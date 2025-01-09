"""Module for handling file and directory operations."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Optional


def write_result_file(out_fname: Path, content: dict) -> bool:
    """Write JSON content to file with error handling and verification."""
    return handle_result_file(out_fname, content)[0]

def handle_result_file(out_fname: Path, content: dict) -> tuple[bool, Optional[str], int]:
    """
    Write result file and track winner status based on edited files and patch length.
    Returns: (success, winner_file, num_edited_files)
    """
    json_content = json.dumps(content, indent=4)
    print(f"Writing to {out_fname} with content length: {len(json_content)}")

    try:
        out_fname.write_text(json_content)
        if not out_fname.exists():
            print(f"ERROR: File {out_fname} does not exist after write attempt!")
            return False, None, 0
            
        print(f"Successfully wrote to {out_fname}")
        print(f"File size: {out_fname.stat().st_size} bytes")
        
        edited_files = content.get("edited_files", [])
        return True, str(out_fname), len(edited_files)
        
    except Exception as e:
        print(f"Error writing to {out_fname}: {str(e)}")
        return False, None, 0


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
