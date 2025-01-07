import json
import random
from datetime import datetime
import uuid
import os
from datetime import datetime
import lox
import tempfile
from pathlib import Path

from swe_lite_ra_aid.utils import load_predictions
from .git import diff_versus_commit, files_in_patch, checkout_repo
from datasets import load_dataset
from ra_aid.agent_utils import run_research_agent
from ra_aid.llm import initialize_llm

REPOS_DNAME = Path("repos")
PREDS_DNAME = Path("predictions")
MAX_RETRIES = 3
MAX_THREADS = 3

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


def process_single_attempt(task, attempt, git_tempdir):
    """Process a single attempt at solving the task"""
    repo = checkout_repo(git_tempdir, task)
    original_cwd = Path.cwd()
    os.chdir(git_tempdir)

    config = get_agent_config()
    full_prompt = prepare_prompt(task)

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

    repo.git.add("-A")
    model_patch = diff_versus_commit(git_tempdir, task["base_commit"])
    print(f"model_patch={model_patch}")
    edited_files = files_in_patch(model_patch)
    print(f"edited_files={edited_files}")

    os.chdir(original_cwd)

    return model_patch, edited_files, research_result


def ra_aid_prediction(task, out_fname):
    """Process one task using RA-AID approach with retries and result tracking"""
    print_task_info(task)
    results = []

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Attempt {attempt} for {task['instance_id']}")

        try:
            with tempfile.TemporaryDirectory() as git_tempdir:
                model_patch, edited_files, research_result = process_single_attempt(
                    task, attempt, git_tempdir
                )

                result = create_result_dict(
                    task, model_patch, edited_files, research_result, attempt
                )
                results.append(result)

                if model_patch:
                    break

        except Exception as e:
            print(f"Error processing {task['instance_id']}: {str(e)}")
            continue

    # Pick the result with most changes as the winner
    winner = max(results, key=lambda r: len(r.get("edited_files", [])) if r else 0)

    # Save results using the provided filename
    json_content = json.dumps(winner, indent=4)
    print(f"Writing to {out_fname} with content length: {len(json_content)}")
    
    try:
        out_fname.write_text(json_content)
        if out_fname.exists():
            print(f"Successfully wrote to {out_fname}")
            print(f"File size: {out_fname.stat().st_size} bytes")
        else:
            print(f"ERROR: File {out_fname} does not exist after write attempt!")
    except Exception as e:
        print(f"Error writing to {out_fname}: {str(e)}")

    return winner


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
        instance_id = task["instance_id"]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prediction_filename = f"{instance_id}-{timestamp}.json"

        # Run prediction with retries and temp dirs
        result = ra_aid_prediction(task, out_dname / prediction_filename)
        return {"instance_id": task["instance_id"], "result": result}
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
                scatter(task, out_dname)
            except KeyboardInterrupt:
                print("\nInterrupted by user. Cleaning up...")
                raise
            except Exception as e:
                print(f"Error processing task: {e}")
                continue

        if MAX_THREADS > 1:
            try:
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
