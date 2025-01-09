import json
import os
import random
from datetime import datetime
import lox
import tempfile
import logging
import subprocess
from pathlib import Path

from swe_lite_ra_aid.utils import load_predictions
from typing import List
from .git import files_in_patch
from .repo_manager import RepoManager
from datasets import load_dataset
from .agent_runner import (
    initialize_model,
    create_result_dict,
    uv_run_raaid,
)
from .prompts import prepare_planning_prompt
from .io_utils import write_result_file, setup_directories, change_directory

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


def process_single_attempt(task, attempt, repo_manager):
    """Process a single attempt at solving the task"""
    github_url = "https://github.com/"
    repo_url = github_url + task["repo"]
    
    # Get/setup cached base repo
    base_repo, cache_path = repo_manager.ensure_base_repo(
        repo_url,
        task["environment_setup_commit"]
    )
    
    # Create worktree for this attempt
    worktree_path, venv_path = repo_manager.create_worktree(
        base_repo, 
        task["base_commit"]
    )
    
    print(f"Using worktree at: {worktree_path}")
    
    try:
        # Use context manager for directory changes
        with change_directory(worktree_path):
            planning_prompt = prepare_planning_prompt(task)
            os.environ["AIDER_MODEL"] = "openrouter/deepseek/deepseek-chat"

            # Run RA.Aid
            model_patch = uv_run_raaid(worktree_path, planning_prompt)
            if not model_patch:
                print("No changes made by RA.Aid")
                return None, [], None

            edited_files = files_in_patch(model_patch)
            print(f"edited_files={edited_files}")

            return model_patch, edited_files, None

    except Exception as e:
        print(f"Error in process_single_attempt: {str(e)}")
        raise
    finally:
        # Cleanup worktree
        repo_manager.cleanup_worktree(base_repo, worktree_path)

        except Exception as e:
            print(f"Error in process_single_attempt: {str(e)}")
            raise


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


def generate_predictions(dataset, out_dname, repo_manager):
    """Generate predictions with parallel processing and result tracking"""
    setup_directories(out_dname, REPOS_DNAME)
    done_instances = get_completed_instances(out_dname)
    remaining_instances = get_remaining_tasks(dataset, done_instances)

    scatter = lambda task: process_task(task, out_dname, repo_manager)
    gather = None

    if MAX_THREADS > 1:
        process_task_lox = lox.process(MAX_THREADS)(scatter)
        scatter = process_task_lox.scatter
        gather = process_task_lox.gather

    try:
        for task in remaining_instances:
            try:
                if MAX_THREADS > 1:
                    scatter(task)
                else:
                    scatter(task)
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
        
        # Initialize repo manager
        repo_manager = RepoManager(REPOS_DNAME)
        
        # Update generate_predictions to pass repo_manager
        generate_predictions(dataset, out_dname, repo_manager)

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
