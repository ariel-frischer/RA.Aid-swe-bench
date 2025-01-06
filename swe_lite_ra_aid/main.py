import json
import uuid
import fcntl
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from git import Repo
from datasets import load_dataset
from ra_aid.agent_utils import (
    run_research_agent,
    # run_planning_agent,
    # run_task_implementation_agent,
)
from ra_aid.llm import initialize_llm

REPOS_DNAME = Path("repos")
PREDS_DNAME = Path("predictions")
MAX_RETRIES = 3


def diff_versus_commit(git_dname, commit):
    """
    Take a diff of `git_dname` current contents versus the `commit`.
    """
    repo = Repo(git_dname)
    diff = repo.git.diff(commit)
    return diff


def files_in_patch(patch):
    """
    Extract the list of modified files from a unified diff patch string.
    """
    files = []
    for line in patch.split("\n"):
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            fname = line.split("/", 1)[1]
            if fname not in files:
                files.append(fname)
    return files


# Initialize the model
model = initialize_llm(provider="openrouter", model_name="deepseek/deepseek-chat")


def ra_aid_prediction(task, out_dname):
    """Process one task using RA-AID approach with retries and result tracking"""
    instance_id = task["instance_id"]
    base_commit = task["base_commit"]
    problem_statement = task["problem_statement"]

    results = []
    cost = 0

    # Do MAX_RETRIES tries until we find a solution with changes
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Attempt {attempt} for {instance_id}")

        try:
            # Get or create repo clone
            repo_path = clone_repository(task["repo"])
            repo = Repo(repo_path)

            # Checkout base commit
            repo.git.checkout(base_commit)

            # Change working directory to the repo
            original_cwd = Path.cwd()
            os.chdir(repo_path)

            # Prepare the full prompt
            full_prompt = f"""
            Repository: {task["repo"]}
            Problem Statement: {problem_statement}
            Base Commit: {base_commit}

            Code Changes (Patch):
            {task["patch"]}

            Test Changes:
            {task["test_patch"]}

            Additional Hints:
            {task.get("hints_text", "")}
            """

            # Setup configuration
            config = {
                "expert_enabled": False,
                "hil": False,
                "web_research_enabled": True,
                "configurable": {"thread_id": str(uuid.uuid4())},
                "recursion_limit": 100,
                "research_only": False,
                "cowboy_mode": True,
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

            # planning_result = run_planning_agent(
            #     base_task=full_prompt,
            #     model=model,
            #     expert_enabled=config["expert_enabled"],
            #     hil=config["hil"],
            #     config=config,
            # )
            # print(f"planning_result={planning_result}")

            # implementation_result = run_task_implementation_agent(
            #     base_task=full_prompt,
            #     model=model,
            #     expert_enabled=config["expert_enabled"],
            #     config=config,
            # )

            # Get the diff between current state and original commit
            model_patch = diff_versus_commit(repo_path, base_commit)
            edited_files = files_in_patch(model_patch)

            # Restore original working directory
            os.chdir(original_cwd)

            # Record the results
            result = {
                "instance_id": instance_id,
                "model_patch": model_patch,
                "edited_files": edited_files,
                "research": research_result,
                "attempt": attempt,
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




def clone_repository(repo_name):
    """Clone a GitHub repository and return the local path with thread-safe locking"""
    repo_url = f"https://github.com/{repo_name}.git"
    REPOS_DNAME.mkdir(exist_ok=True)
    clone_dir = REPOS_DNAME / repo_name.replace("/", "_")

    # Use a lock file to prevent multiple workers from cloning the same repo
    lock_file = clone_dir.with_suffix(".lock")
    lock_file.touch()

    with open(lock_file, "r+") as f:
        try:
            # Acquire an exclusive lock
            fcntl.flock(f, fcntl.LOCK_EX)

            if not clone_dir.exists():
                print(f"Cloning repository: {repo_url}")
                repo = Repo.clone_from(repo_url, clone_dir)
                # Set git config to suppress detached HEAD warning
                repo.config_writer().set_value("advice", "detachedHead", "false").release()
            else:
                print(f"Using existing repository: {clone_dir}")
                repo = Repo(clone_dir)

        finally:
            # Release the lock
            fcntl.flock(f, fcntl.LOCK_UN)

    return str(clone_dir)


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
        return {"id": task["id"], "instance_id": task["instance_id"], "result": result}
    except Exception as e:
        print(f"Error processing task {task.get('instance_id')}: {str(e)}")
        return {"id": task["id"], "instance_id": task["instance_id"], "error": str(e)}


# Generate predictions for SWE-bench Lite
def generate_predictions(dataset, max_workers, out_dname):
    """Generate predictions with parallel processing and result tracking"""
    predictions = []

    # Create output directory if it doesn't exist
    out_dname.mkdir(exist_ok=True)

    # Create repos directory if it doesn't exist
    REPOS_DNAME.mkdir(exist_ok=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_task, task, out_dname) for task in dataset]
        for i, future in enumerate(futures):
            print(f"Processing task {i+1}/{len(dataset)}")
            predictions.append(future.result())
    return predictions


def main():
    # Load the dataset
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    # Create output directory with timestamp
    out_dname = PREDS_DNAME / "ra_aid_predictions"

    # Set the number of workers
    max_workers = 1

    # Generate and save predictions
    predictions = generate_predictions(dataset, max_workers, out_dname)

    # Save all predictions to a single file
    predictions_path = out_dname / "all_predictions.jsonl"
    with open(predictions_path, "w") as f:
        for pred in predictions:
            f.write(json.dumps(pred) + "\n")

    print(f"Predictions saved to {predictions_path}")


if __name__ == "__main__":
    main()


## Dataset Structure
# Data Instances
#
# An example of a SWE-bench datum is as follows:
# instance_id: (str) - A formatted instance identifier, usually as repo_owner__repo_name-PR-number.
# patch: (str) - The gold patch, the patch generated by the PR (minus test-related code), that resolved the issue.
# repo: (str) - The repository owner/name identifier from GitHub.
# base_commit: (str) - The commit hash of the repository representing the HEAD of the repository before the solution PR is applied.
# hints_text: (str) - Comments made on the issue prior to the creation of the solution PR’s first commit creation date.
# created_at: (str) - The creation date of the pull request.
# test_patch: (str) - A test-file patch that was contributed by the solution PR.
# problem_statement: (str) - The issue title and body.
# version: (str) - Installation version to use for running evaluation.
# environment_setup_commit: (str) - commit hash to use for environment setup and installation.
# FAIL_TO_PASS: (str) - A json list of strings that represent the set of tests resolved by the PR and tied to the issue resolution.
# PASS_TO_PASS: (str) - A json list of strings that represent tests that should pass before and after the PR application.
