import json
import uuid
import fcntl
import os
import lox
import tempfile
import shutil
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
            with tempfile.TemporaryDirectory(dir="/mnt/aider") as git_tempdir:
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

            # Stage all changes and get the diff
            repo.git.add("-A")  # Add all changes including new/deleted files
            model_patch = diff_versus_commit(repo_path, base_commit)
            print(f"model_patch={model_patch}")
            edited_files = files_in_patch(model_patch)
            print(f"edited_files={edited_files}")

                # Restore original working directory
                os.chdir(original_cwd)
            # Temporary directory is automatically cleaned up when the with block exits

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


def checkout_repo_url_commit(git_tempdir, repo_url, commit):
    """
    Clone the git repo from url into tempdir at specific commit.
    """
    repo = Repo.clone_from(repo_url, git_tempdir)
    repo.git.checkout(commit)
    return repo

def checkout_repo(git_tempdir, entry):
    """
    Clone the SWE Bench entry's git `repo` into `dname` at the `base_commit`.
    Make a tempdir if no `dname` provided.
    """
    github_url = "https://github.com/"
    repo_url = github_url + entry["repo"]
    commit = entry["base_commit"]

    print(f"Cloning {repo_url} at commit {commit}")
    return checkout_repo_url_commit(git_tempdir, repo_url, commit)
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
                repo.config_writer().set_value(
                    "advice", "detachedHead", "false"
                ).release()
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

    if threads > 1:
        process_task_lox = lox.process(threads)(process_task)
        process_task_func = process_task_lox.scatter
        gather = process_task_lox.gather
    else:
        process_task_func = process_task

    try:
        # Process all tasks
        for task in dataset:
            # Check if prediction already exists
            instance_id = task["instance_id"]
            existing_predictions = list(out_dname.glob(f"*{instance_id}.json"))
            if existing_predictions:
                print(f"Skipping {instance_id} - prediction already exists")
                continue
                
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
        # Load the dataset
        dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

        # Create output directory with timestamp
        out_dname = PREDS_DNAME / "ra_aid_predictions"

        # Set the number of threads (1 for now)
        threads = 1

        # Generate and save predictions
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
