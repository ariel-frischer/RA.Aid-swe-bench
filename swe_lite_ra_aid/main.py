import json
import random
import uuid
import os
from datetime import datetime
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

# Initialize the model
model = initialize_llm(provider="openrouter", model_name="deepseek/deepseek-chat")


def ra_aid_prediction(task, out_dname):
    """Process one task using RA-AID approach with retries and result tracking"""
    instance_id = task["instance_id"]
    print(f"instance_id={instance_id}")
    base_commit = task["base_commit"]
    print(f"base_commit={base_commit}")
    problem_statement = task["problem_statement"]
    print(f"problem_statement={problem_statement}")

    results = []
    cost = 0

    # Do MAX_RETRIES tries until we find a solution with changes
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Attempt {attempt} for {instance_id}")

        try:
            # Create temporary directory and clone repo
            with tempfile.TemporaryDirectory() as git_tempdir:
                repo = checkout_repo(git_tempdir, task)

                # Change working directory to the repo
                original_cwd = Path.cwd()
                os.chdir(git_tempdir)

                # Prepare the full prompt
                full_prompt = f"""
                Repository: {task["repo"]}

                Base Commit: {base_commit}
                Code Changes (Patch):
                {task["patch"]}

                Test Changes:
                {task["test_patch"]}

                <Problem Statement>:
                {problem_statement}
                </Problem Statement>

                Additional Hints:
                {task.get("hints_text", "")}

                You are a world class software engineer. 
                You must make code changes to fix the issue described in the problem statement.
                """

                # Setup configuration
                config = {
                    "expert_enabled": True,
                    "hil": False,
                    "web_research_enabled": True,
                    "configurable": {"thread_id": str(uuid.uuid4())},
                    "recursion_limit": 100,
                    "research_only": False,
                    "cowboy_mode": True,
                    # "expert_provider": "anthropic",
                    # "expert_model": "claude-3-5-sonnet-20241022",
                }

                # Run all agents
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

                # Stage all changes and get the diff
                repo.git.add("-A")  # Add all changes including new/deleted files
                model_patch = diff_versus_commit(git_tempdir, base_commit)
                print(f"model_patch={model_patch}")
                edited_files = files_in_patch(model_patch)
                print(f"edited_files={edited_files}")

                os.chdir(original_cwd)

                result = {
                    "instance_id": instance_id,
                    "model_name_or_path": "ra-aid-model",
                    "model_patch": model_patch + "\n" if model_patch else "",
                    "edited_files": edited_files,
                    "research": research_result,
                    "attempt": attempt,
                    "timestamp": datetime.now().isoformat(),
                    "ra_aid_model": "openrouter/deepseek/deepseek-chat",
                    "ra_aid_editor": "anthropic/claude-3-5-sonnet-20241022",
                }
                results.append(result)

                # If we got changes, return the result
                if model_patch:
                    break

        except Exception as e:
            print(f"Error processing {instance_id}: {str(e)}")
            continue

    # Pick the result with most changes as the winner
    winner = max(results, key=lambda r: len(r.get("edited_files", [])) if r else 0)

    # Save results
    out_fname = out_dname / (instance_id + ".json")
    out_fname.write_text(json.dumps(winner, indent=4))

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
        # Run prediction with retries and temp dirs
        result = ra_aid_prediction(task, out_dname)
        return {"instance_id": task["instance_id"], "result": result}
    except Exception as e:
        print(f"Error processing task {task.get('instance_id')}: {str(e)}")
        return {"id": task["id"], "instance_id": task["instance_id"], "error": str(e)}


def generate_predictions(dataset, threads, out_dname):
    """Generate predictions with parallel processing and result tracking"""
    # Create output directory if it doesn't exist
    out_dname.mkdir(exist_ok=True)

    # Create repos directory if it doesn't exist 
    REPOS_DNAME.mkdir(exist_ok=True)

    # Load existing predictions to skip already processed instances
    done_preds = load_predictions([out_dname])
    done_instances = {inst for inst, pred in done_preds.items() 
                     if pred.get("model_patch") and pred.get("edited_files")}
    print(f"Found {len(done_instances)} completed predictions")
    print(f"Skipping {len(done_instances)} already processed instances")

    # Get remaining instances to process
    remaining_instances = [task for task in dataset 
                         if task["instance_id"] not in done_instances]
    random.shuffle(remaining_instances)
    print(f"Processing {len(remaining_instances)} remaining instances")

    if threads > 1:
        process_task_lox = lox.process(threads)(process_task)
        process_task_func = process_task_lox.scatter
        gather = process_task_lox.gather
    else:
        process_task_func = process_task

    try:
        # Process remaining tasks
        for task in remaining_instances:
            # Get instance ID and create timestamped filename
            instance_id = task["instance_id"]
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            prediction_filename = f"{instance_id}-{timestamp}.json"

            # Proceed with processing the task

            try:
                process_task_func(task, out_dname)
            except KeyboardInterrupt:
                print("\nInterrupted by user. Cleaning up...")
                raise
            except Exception as e:
                print(f"Error processing task: {e}")
                continue

        if threads > 1:
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
        threads = 5

        generate_predictions(dataset, threads, out_dname)

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


