import json
import random
from datetime import datetime
import uuid
import os
import lox
import tempfile
from pathlib import Path

from swe_lite_ra_aid.utils import load_predictions
from .git import diff_versus_commit, files_in_patch, checkout_repo
from datasets import load_dataset
from ra_aid.agent_utils import run_planning_agent, run_research_agent
from ra_aid.llm import initialize_llm

REPOS_DNAME = Path("repos")
PREDS_DNAME = Path("predictions")
MAX_ATTEMPTS = 3
MAX_THREADS = 2

# Initialize the model
model = initialize_llm(provider="openrouter", model_name="deepseek/deepseek-chat")


def print_task_info(task):
    """Print basic task information"""
    print(f"instance_id={task['instance_id']}")
    print(f"base_commit={task['base_commit']}")
    print(f"problem_statement={task['problem_statement']}")


def prepare_prompt(task):
    """Prepare the full prompt for the research agent"""
    return f"""
    Repository: {task["repo"]}

    Base Commit: {task["base_commit"]}
    Code Changes (Patch):
    {task["patch"]}

    Test Changes:
    {task["test_patch"]}

    <Problem Statement>:
    {task["problem_statement"]}
    </Problem Statement>

    Additional Hints:
    {task.get("hints_text", "")}

    You are a world class software engineer. 
    You must make code changes to fix the issue described in the problem statement.
    """


def get_agent_config():
    """Get configuration for research agent"""
    return {
        "expert_enabled": False,
        "hil": False,
        "web_research_enabled": True,
        "configurable": {"thread_id": str(uuid.uuid4())},
        "recursion_limit": 50,
        "research_only": False,
        "cowboy_mode": True,
    }


def create_result_dict(task, model_patch, edited_files, research_result, attempt):
    """Create standardized result dictionary"""
    return {
        "instance_id": task["instance_id"],
        "model_name_or_path": "ra-aid-model",
        "model_patch": model_patch + "\n" if model_patch else "",
        "edited_files": edited_files,
        "research": research_result,
        "attempt": attempt,
        "timestamp": datetime.now().isoformat(),
        "ra_aid_model": "openrouter/deepseek/deepseek-chat",
        "ra_aid_editor": "openrouter/deepseek/deepseek-chat",
    }


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
    
    # Clone repository first
    repo = checkout_repo(git_tempdir, task)
    
    config = get_agent_config()
    full_prompt = prepare_prompt(task)
    
    # Use context manager for directory changes
    with change_directory(git_tempdir_path):
        try:
            research_result = run_research_agent(
                base_task_or_query=full_prompt,
                model=model,
                expert_enabled=config["expert_enabled"],
                research_only=config["research_only"],
                hil=config["hil"],
                web_research_enabled=config["web_research_enabled"],
                config=config,
            )
            print(f"research_result={research_result}")

            print(diff_versus_commit(git_tempdir, task["base_commit"]))

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
                # Ensure the directory exists
                Path(git_tempdir).mkdir(parents=True, exist_ok=True)
                print(f"Directory exists: {Path(git_tempdir).exists()}")
            
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
        # Create timestamped filename
        # instance_id = task["instance_id"]
        # timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        # Run prediction with retries and temp dirs
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
        # Rebind process_task to use `threads` concurrency
        process_task_lox = lox.process(MAX_THREADS)(process_task)
        scatter = process_task_lox.scatter
        gather = process_task_lox.gather

    try:
        # Process remaining tasks
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
