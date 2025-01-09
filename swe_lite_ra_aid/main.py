from contextlib import contextmanager
import json
import random
from datetime import datetime
import uuid
import os
import lox
import tempfile
import logging
import subprocess
from pathlib import Path

from swe_lite_ra_aid.utils import load_predictions
from typing import List
from .git import diff_versus_commit, files_in_patch, checkout_repo
from datasets import load_dataset
from .agent_runner import initialize_model, run_agents, create_result_dict

REPOS_DNAME = Path("repos")
PREDS_DNAME = Path("predictions")
MAX_ATTEMPTS = 3
MAX_THREADS = 1

model = initialize_model()

def uv_venv(repo_dir: Path, repo_name: str, force_venv: bool = False) -> None:
    """Create a virtual environment using uv."""
    venv_path = repo_dir / ".venv"
    if venv_path.exists() and not force_venv:
        logging.info(f"Virtual environment already exists at {venv_path}")
        return

    cmd = ["uv", "venv", ".venv"]
    subprocess.run(cmd, cwd=repo_dir, check=True)

def uv_pip_install(repo_dir: Path, args: List[str]) -> None:
    """Run uv pip install with given arguments."""
    cmd = ["uv", "pip", "install"] + args
    subprocess.run(cmd, cwd=repo_dir, check=True)

def setup_venv_and_deps(repo_dir: Path, repo_name: str, force_venv: bool) -> None:
    """
    - uv venv .venv --python=xxx (optional)
    - uv pip install --upgrade pip
    - uv pip install --upgrade setuptools wheel  (so pkg_resources etc. are available)
    - uv pip install -e <ra-aid local path>
    - If pyproject.toml -> uv pip install .
    - If requirements.txt -> uv pip install -r requirements.txt
    - If requirements-dev.txt -> uv pip install -r requirements-dev.txt
    - If there's a setup.py or pyproject => uv pip install -e .
    """
    uv_venv(repo_dir, repo_name, force_venv)

    # 1) upgrade pip
    uv_pip_install(repo_dir, ["--upgrade", "pip"])

    # 2) ensure setuptools & wheel are installed/up to date
    uv_pip_install(repo_dir, ["--upgrade", "setuptools", "wheel"])

    # 3) install ra-aid from local path
    script_dir = Path(__file__).resolve().parent
    ra_aid_root = script_dir.parent  # one level up from scripts
    uv_pip_install(repo_dir, ["-e", str(ra_aid_root)])

    # 4) optional pyproject
    pyproject_path = repo_dir / "pyproject.toml"
    if pyproject_path.is_file():
        uv_pip_install(repo_dir, ["."])

    # 5) optional requirements.txt
    req_file = repo_dir / "requirements.txt"
    if req_file.is_file():
        uv_pip_install(repo_dir, ["-r", "requirements.txt"])

    # 6) optional requirements-dev.txt
    req_dev_file = repo_dir / "requirements-dev.txt"
    if req_dev_file.is_file():
        uv_pip_install(repo_dir, ["-r", "requirements-dev.txt"])

    # 7) install the cloned project in editable mode if it's a Python package
    setup_path = repo_dir / "setup.py"
    if pyproject_path.is_file() or setup_path.is_file():
        logging.info("Installing cloned project in editable mode.")
        uv_pip_install(repo_dir, ["-e", "."])

def print_task_info(task):
    """Print basic task information"""
    print(f"instance_id={task['instance_id']}")
    print(f"base_commit={task['base_commit']}")
    print(f"problem_statement={task['problem_statement']}")


def build_prompt(problem_statement: str, fail_tests: list, pass_tests: list) -> str:
    """Construct the prompt text from problem_statement, FAIL_TO_PASS, PASS_TO_PASS."""
    prompt = f"{problem_statement}\n\nTests that need to be fixed:\n```\n"
    for t in fail_tests:
        prompt += f"- {t}\n"
    prompt += "```\n\n"
    if pass_tests:
        prompt += "Tests that must remain passing:\n```\n"
        for t in pass_tests:
            prompt += f"- {t}\n"
        prompt += "```\n\n"
    prompt += "\n\nYou must run all above tests both **before and after** making changes, and ensure they pass as you do your work. Do not write any new test cases."
    return prompt


def prepare_base_prompt(task):
    """Prepare the common base prompt used by both agents"""
    fail_tests = json.loads(task["FAIL_TO_PASS"])
    pass_tests = json.loads(task["PASS_TO_PASS"])

    problem_details = build_prompt(task["problem_statement"], fail_tests, pass_tests)

    return f"""
    Repository: {task["repo"]}

    Base Commit: {task["base_commit"]}
    Code Changes (Patch):
    {task["patch"]}

    Test Changes:
    {task["test_patch"]}

    <Problem Statement and Tests>:
    {problem_details}
    </Problem Statement and Tests>

    Additional Hints:
    {task.get("hints_text", "")}"""


def prepare_research_prompt(task):
    """Prepare the prompt specifically for the research agent"""
    base_prompt = prepare_base_prompt(task)
    return (
        base_prompt
        + """

    You are a research assistant tasked with finding all relevant context and information needed to solve this issue.
    You must be comprehensive and thorough in gathering information about the codebase, related issues, and potential solutions.
    """
    )


def prepare_planning_prompt(task):
    """Prepare the prompt specifically for the planning agent"""
    base_prompt = prepare_base_prompt(task)
    return (
        base_prompt
        + """

    You are a world class software engineer.
    You must make code changes to fix the issue described in the problem statement.
    """
    )



@contextmanager
def change_directory(path):
    """Context manager for changing directory"""
    original_cwd = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


def process_single_attempt(task, attempt, git_tempdir):
    """Process a single attempt at solving the task"""
    git_tempdir_path = Path(git_tempdir)
    print(f"Using temporary directory: {git_tempdir_path.absolute()}")

    # Clone repository at environment setup commit
    repo = checkout_repo(git_tempdir, task)
    
    config = get_agent_config()
    research_prompt = prepare_research_prompt(task)
    planning_prompt = prepare_planning_prompt(task)

    # Use context manager for directory changes
    with change_directory(git_tempdir_path):
        # Setup virtual environment and dependencies
        setup_venv_and_deps(Path.cwd(), task["repo"], force_venv=False)
        print(f"Switching to base commit {task['base_commit']}")
        repo.git.checkout(task['base_commit'])

        try:
            research_result, planning_result = run_agents(research_prompt, planning_prompt, model)

            # Add all changes - otherwise diff doesnt work correctly
            repo.git.add("-A")
            model_patch = diff_versus_commit(git_tempdir, task["base_commit"])

            edited_files = files_in_patch(model_patch)
            print(f"edited_files={edited_files}")

            return model_patch, edited_files, research_result

        except Exception as e:
            print(f"Error in process_single_attempt: {str(e)}")
            raise


def write_result_file(out_fname, content):
    """Write JSON content to file with error handling and verification"""
    json_content = json.dumps(content, indent=4)
    print(f"Writing to {out_fname} with content length: {len(json_content)}")

    try:
        out_fname.write_text(json_content)
        if out_fname.exists():
            print(f"Successfully wrote to {out_fname}")
            print(f"File size: {out_fname.stat().st_size} bytes")
            return True
        else:
            print(f"ERROR: File {out_fname} does not exist after write attempt!")
            return False
    except Exception as e:
        print(f"Error writing to {out_fname}: {str(e)}")
        return False


def ra_aid_prediction(task, out_dname):
    """Process one task using RA-AID approach with retries and result tracking"""
    print_task_info(task)
    results = []
    output_files = []
    winner_file = None
    max_edited_files = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print("=" * 60)
        print(f"Attempt {attempt} for {task['instance_id']}")
        print("=" * 60)

        try:
            with tempfile.TemporaryDirectory() as git_tempdir:
                print(f"Created temporary directory: {git_tempdir}")
                Path(git_tempdir).mkdir(parents=True, exist_ok=True)

                model_patch, edited_files, research_result = process_single_attempt(
                    task, attempt, str(Path(git_tempdir).absolute())
                )

                print("Successfully completed process_single_attempt")

                result = create_result_dict(
                    task, model_patch, edited_files, research_result, attempt
                )
                results.append(result)

                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                attempt_fname = (
                    out_dname
                    / f"{task['instance_id']}-attempt{attempt}-{timestamp}.json"
                )

                if write_result_file(attempt_fname, result):
                    output_files.append(attempt_fname)
                    # Track the file with most edits as the winner
                    if len(edited_files) > max_edited_files:
                        max_edited_files = len(edited_files)
                        winner_file = attempt_fname

                if model_patch:
                    break

        except Exception as e:
            print(f"Error processing {task['instance_id']}: {str(e)}")
            continue

    if winner_file:
        print(
            f"Winner file selected: {winner_file} with {max_edited_files} edited files"
        )
    else:
        print("No successful attempts with edited files")

    return {
        "output_files": output_files,
        "winner_file": winner_file,
        "max_edited_files": max_edited_files,
    }


def process_task(task, out_dname):
    """Process one task with proper error handling and result tracking"""
    if isinstance(task, str):
        try:
            task = json.loads(task)
        except json.JSONDecodeError:
            task = {"raw_input": task}

    print(f"\nProcessing task {task.get('instance_id', 'unknown')}")

    try:
        result = ra_aid_prediction(task, out_dname)
        return {
            "instance_id": task["instance_id"],
            "result": result,
            "output_files": result["output_files"],
            "winner_file": result["winner_file"],
        }
    except Exception as e:
        print(f"Error processing task {task.get('instance_id')}: {str(e)}")
        return {"id": task["id"], "instance_id": task["instance_id"], "error": str(e)}


def setup_directories(out_dname):
    """Create necessary directories for predictions and repos"""
    out_dname.mkdir(exist_ok=True)
    REPOS_DNAME.mkdir(exist_ok=True)


def get_completed_instances(out_dname):
    """Load and return set of already processed instance IDs"""
    done_preds = load_predictions([out_dname])
    done_instances = {
        inst
        for inst, pred in done_preds.items()
        if pred.get("model_patch") and pred.get("edited_files")
    }
    print(f"Found {len(done_instances)} completed predictions")
    print(f"Skipping {len(done_instances)} already processed instances")
    return done_instances


def get_remaining_tasks(dataset, done_instances):
    """Get shuffled list of remaining tasks to process"""
    remaining_instances = [
        task for task in dataset if task["instance_id"] not in done_instances
    ]
    random.shuffle(remaining_instances)
    print(f"Processing {len(remaining_instances)} remaining instances")
    return remaining_instances


def generate_predictions(dataset, out_dname):
    """Generate predictions with parallel processing and result tracking"""
    setup_directories(out_dname)
    done_instances = get_completed_instances(out_dname)
    remaining_instances = get_remaining_tasks(dataset, done_instances)

    scatter = process_task
    gather = None

    if MAX_THREADS > 1:
        process_task_lox = lox.process(MAX_THREADS)(process_task)
        scatter = process_task_lox.scatter
        gather = process_task_lox.gather

    try:
        for task in remaining_instances:
            try:
                if MAX_THREADS > 1:
                    scatter(task, out_dname)
                else:
                    process_task(task, out_dname)
            except KeyboardInterrupt:
                print("\nInterrupted by user. Cleaning up...")
                raise
            except Exception as e:
                print(f"Error processing task: {e}")
                continue

        if MAX_THREADS > 1:
            try:
                print(f"Running {MAX_THREADS} threads.")
                gather()
            except KeyboardInterrupt:
                print("\nInterrupted by user during gather. Cleaning up...")
                raise
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
        return


def main():
    try:
        dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        out_dname = PREDS_DNAME / "ra_aid_predictions"

        generate_predictions(dataset, out_dname)

        print(f"Predictions saved to {out_dname}")
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        return 1
    except Exception as e:
        print(f"An error occurred: {e}")
        return 1
    return 0


if __name__ == "__main__":
    main()
