import json
import os
import random
import lox
import tempfile
import argparse
from pathlib import Path
from .logger import logger

from swe_lite_ra_aid.utils import load_predictions
from .git import files_in_patch, stage_and_get_patch
from .repo_manager import RepoManager
from datasets import load_dataset
from .config import (
    RA_AID_AIDER_MODEL,
    REPOS_DNAME,
    PREDS_DNAME,
    MAX_ATTEMPTS,
    MAX_THREADS,
    SUBMISSION_MODE,
)
from .agent_runner import (
    create_result_dict,
    run_ra_aid,
)
from .prompts import prepare_planning_prompt
from .io_utils import (
    setup_directories,
    change_directory,
    handle_result_file,
    update_winner_file,
    save_trajectory,
)


def process_single_attempt(task, _attempt, repo_manager):
    """Process a single attempt at solving the task"""
    github_url = "https://github.com/"
    repo_url = github_url + task["repo"]

    base_repo, _cache_path = repo_manager.ensure_base_repo(
        repo_url, task["environment_setup_commit"], task["version"]
    )

    worktree_path, _venv_path = repo_manager.create_worktree(
        base_repo, task["base_commit"], task["environment_setup_commit"]
    )

    logger.info(f"Using worktree at: {worktree_path}")

    try:
        with change_directory(worktree_path):
            planning_prompt = prepare_planning_prompt(task)
            os.environ["AIDER_MODEL"] = RA_AID_AIDER_MODEL

            if SUBMISSION_MODE:
                os.environ["TAVILY_API_KEY"] = ""

            # Fixes Trajectory file stream readability issues while capturing STDOUT
            os.environ["AIDER_PRETTY"] = "false"
            os.environ["AIDER_STREAM"] = "false"

            trajectory_output, _returncode = run_ra_aid(worktree_path, planning_prompt)

            if not trajectory_output:
                logger.warning("No output from RA.Aid")
                return None, [], None, None

            model_patch = stage_and_get_patch(worktree_path)

            if not model_patch:
                logger.warning("❌ No changes made by RA.Aid")
                return None, [], None, trajectory_output

            edited_files = files_in_patch(model_patch)
            logger.debug(f"edited_files={edited_files}")

            return model_patch, edited_files, None, trajectory_output

    except Exception as e:
        logger.error(f"Error in process_single_attempt: {str(e)}")
        raise
    finally:
        repo_manager.cleanup_worktree(base_repo, worktree_path)


def ra_aid_prediction(task, out_dname, repo_manager):
    """Process one task using RA-AID approach with retries and result tracking"""
    results = []
    output_files = []
    winner_file = None
    max_edited_files = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info("=" * 60)
        logger.info(f"Attempt {attempt} for {task['instance_id']}")
        logger.info("=" * 60)

        try:
            with tempfile.TemporaryDirectory() as git_tempdir:
                Path(git_tempdir).mkdir(parents=True, exist_ok=True)

                model_patch, edited_files, research_result, trajectory_output = (
                    process_single_attempt(task, attempt, repo_manager)
                )
                logger.info("Successfully completed process_single_attempt")

                traj_fname = save_trajectory(
                    out_dname, task, attempt, trajectory_output
                )

                result = create_result_dict(
                    task,
                    model_patch,
                    edited_files,
                    attempt,
                    trajectory_file=traj_fname,
                    repo_manager=repo_manager,
                )
                results.append(result)

                success, result_file, num_edited, attempt_fname = handle_result_file(
                    out_dname, task, attempt, result
                )

                if success:
                    winner_file, max_edited_files = update_winner_file(
                        output_files,
                        attempt_fname,
                        result_file,
                        num_edited,
                        result,
                        winner_file,
                        max_edited_files,
                    )

                if model_patch:
                    break

        except Exception as e:
            error_msg = f"Error processing {task['instance_id']}: {str(e)}"
            logger.error(error_msg)
            
            result = create_result_dict(
                task,
                None,  # model_patch
                [],    # edited_files 
                attempt,
                trajectory_file=None,
                repo_manager=repo_manager,
            )
            result["errors"].append(error_msg)
            results.append(result)

            # Still try to write the result file
            success, result_file, num_edited, attempt_fname = handle_result_file(
                out_dname, task, attempt, result
            )

    if winner_file:
        logger.info(
            f"Winner file selected: {winner_file} with {max_edited_files} edited files"
        )
    else:
        logger.warning("No successful attempts with edited files")

    return {
        "output_files": output_files,
        "winner_file": winner_file,
        "max_edited_files": max_edited_files,
    }


def process_task(task, out_dname, repo_manager):
    """Process one task with proper error handling and result tracking"""
    if isinstance(task, str):
        try:
            task = json.loads(task)
        except json.JSONDecodeError:
            task = {"raw_input": task}

    logger.info(f"\nProcessing task {task.get('instance_id', 'unknown')}")

    try:
        result = ra_aid_prediction(task, out_dname, repo_manager)
        return {
            "instance_id": task["instance_id"],
            "result": result,
            "output_files": result["output_files"],
            "winner_file": result["winner_file"],
        }
    except Exception as e:
        logger.error(f"Error processing task {task.get('instance_id')}: {str(e)}")
        return {"id": task["id"], "instance_id": task["instance_id"], "error": str(e)}


def get_completed_instances(out_dname):
    """Load and return set of already processed instance IDs"""
    done_preds = load_predictions([out_dname])
    done_instances = {
        inst
        for inst, pred in done_preds.items()
        if pred.get("model_patch") and pred.get("edited_files")
    }
    logger.info(f"Found {len(done_instances)} completed predictions")
    logger.info(f"Skipping {len(done_instances)} already processed instances")
    return done_instances


def get_remaining_tasks(dataset, done_instances, filter_repos=None, only_tasks=None):
    """Get shuffled list of remaining tasks to process
    
    Args:
        dataset: The SWE-bench dataset
        done_instances: Set of already processed instance IDs
        filter_repos: Optional list of repo names to filter for (e.g. ["matplotlib/matplotlib"])
        only_tasks: Optional list of specific task IDs to process (e.g. ["scikit-learn__scikit-learn-10297"])
    """
    remaining_instances = [
        task for task in dataset if task["instance_id"] not in done_instances
    ]
    
    if only_tasks:
        remaining_instances = [
            task for task in remaining_instances 
            if task["instance_id"] in only_tasks
        ]
        logger.info(f"Filtered to {len(remaining_instances)} specific tasks: {only_tasks}")
    elif filter_repos:
        remaining_instances = [
            task for task in remaining_instances 
            if any(repo in task["repo"] for repo in filter_repos)
        ]
        logger.info(f"Filtered to {len(remaining_instances)} instances from repos: {filter_repos}")
        
    random.shuffle(remaining_instances)
    logger.info(f"Processing {len(remaining_instances)} remaining instances")
    return remaining_instances


def generate_predictions(dataset, out_dname, repo_manager):
    """Generate predictions with parallel processing and result tracking"""
    setup_directories(out_dname, REPOS_DNAME)
    done_instances = get_completed_instances(out_dname)
    
    # Specify specific tasks to process, comment out to process all tasks
    # only_tasks = ["django__django-14155"]
    only_tasks = None  # Process all tasks
    
    # Only used if only_tasks is None
    # filter_repos = ["scikit-learn/scikit-learn"]
    filter_repos = None
    
    remaining_instances = get_remaining_tasks(dataset, done_instances, filter_repos, only_tasks)

    def scatter(task):
        return process_task(task, out_dname, repo_manager)

    gather = None

    if MAX_THREADS > 1:
        process_task_lox = lox.process(MAX_THREADS)(scatter)
        scatter = process_task_lox.scatter
        gather = process_task_lox.gather

    try:
        for task in remaining_instances:
            if MAX_THREADS > 1:
                scatter(task)
            else:
                process_task(task, out_dname, repo_manager)

        if MAX_THREADS > 1:
            logger.info(f"Running {MAX_THREADS} threads.")
            gather()
    except KeyboardInterrupt:
        logger.warning("\nGracefully shutting down...")
        return


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level"
    )
    parser.add_argument(
        "--minimal-logger",
        action="store_true",
        help="Use minimal logging format without timestamps"
    )
    return parser.parse_args()

def main():
    try:
        args = parse_args()
        logger.setLevel(args.log_level)
        logger.set_minimal(args.minimal_logger)
        
        project_root = Path(__file__).resolve().parent.parent

        dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        out_dname = project_root / PREDS_DNAME / "ra_aid_predictions"

        repo_manager = RepoManager(project_root / REPOS_DNAME)

        generate_predictions(dataset, out_dname, repo_manager)

        logger.info(f"Predictions saved to {out_dname}")
    except KeyboardInterrupt:
        logger.warning("\nProgram terminated by user")
        return 1
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1
    return 0


if __name__ == "__main__":
    main()
