"""Module for handling file and directory operations."""

from contextlib import contextmanager
import json
import os
from pathlib import Path


def write_result_file(out_fname: Path, content: dict) -> bool:
    """Write JSON content to file with error handling and verification."""
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
