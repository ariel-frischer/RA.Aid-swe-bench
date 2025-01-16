"""Module for handling file and directory operations."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
from .logger import logger


def handle_result_file(
    out_dname: Path, task: dict, attempt: int, content: dict
) -> tuple[bool, Optional[str], int, Path]:
    """
    Write result file and track winner status based on edited files and patch length.
    Returns: (success, winner_file, num_edited_files, attempt_fname)
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    attempt_fname = (
        out_dname / f"{task['instance_id']}-attempt{attempt}-{timestamp}.json"
    )

    json_content = json.dumps(content, indent=4)
    logger.info(f"Writing to {attempt_fname} with content length: {len(json_content)}")

    try:
        attempt_fname.write_text(json_content)
        if not attempt_fname.exists():
            logger.error(f"File {attempt_fname} does not exist after write attempt!")
            return False, None, 0, attempt_fname

        logger.info(f"Successfully wrote to {attempt_fname}")
        logger.debug(f"File size: {attempt_fname.stat().st_size} bytes")

        edited_files = content.get("edited_files", [])
        return True, str(attempt_fname), len(edited_files), attempt_fname

    except Exception as e:
        logger.error(f"Error writing to {attempt_fname}: {str(e)}")
        return False, None, 0, None


def update_winner_file(
    output_files: list,
    attempt_fname: Path,
    result_file: str,
    num_edited: int,
    result: dict,
    winner_file: Optional[str],
    max_edited_files: int,
) -> tuple[str, int]:
    """
    Update winner file based on number of edited files and patch length.
    Updates is_winner field in both current and previous winner files.
    (WIP) Useful for prediction tracking if MAX_ATTEMPTS > 1, field is not used in report.py yet
    Returns: (winner_file, max_edited_files)
    """
    output_files.append(attempt_fname)

    new_winner = False
    if num_edited > max_edited_files:
        max_edited_files = num_edited
        new_winner = True
    elif num_edited == max_edited_files and winner_file:
        current_patch = result.get("model_patch", "")
        with open(winner_file) as f:
            winner_result = json.loads(f.read())
            winner_patch = winner_result.get("model_patch", "")
        if len(current_patch) > len(winner_patch):
            new_winner = True

    if new_winner:
        # Unset previous winner if it exists
        if winner_file:
            with open(winner_file) as f:
                prev_winner = json.loads(f.read())
            prev_winner["is_winner"] = False
            with open(winner_file, "w") as f:
                json.dump(prev_winner, f, indent=4)

        # Set new winner
        result["is_winner"] = True
        with open(result_file, "w") as f:
            json.dump(result, f, indent=4)
        winner_file = result_file
    else:
        # Ensure current file is marked as not winner
        result["is_winner"] = False
        with open(result_file, "w") as f:
            json.dump(result, f, indent=4)

    return winner_file, max_edited_files


def setup_directories(out_dname: Path, repos_dname: Path) -> None:
    """Create necessary directories for predictions and repos."""
    out_dname.mkdir(exist_ok=True)
    repos_dname.mkdir(exist_ok=True)


@contextmanager
def change_directory(path: Path):
    """Context manager for changing directory."""
    original_cwd = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


def save_trajectory(
    out_dname: Path, task: dict, attempt: int, trajectory_output: str
) -> Optional[Path]:
    """Save trajectory output to a file and return the filename."""
    if not trajectory_output:
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    traj_fname = (
        out_dname / f"traj_{task['instance_id']}_attempt{attempt}_{timestamp}.txt"
    )
    traj_fname.write_text(trajectory_output)
    logger.info(f"Saved trajectory to {traj_fname}")
    return traj_fname
