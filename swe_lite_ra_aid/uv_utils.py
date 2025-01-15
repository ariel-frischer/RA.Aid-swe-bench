"""Module for handling UV virtual environment setup and package installation."""

import os
from pathlib import Path
import logging
import subprocess
from typing import List, Optional
from .io_utils import change_directory


def get_python_version(repo: str, instance_version: str) -> Optional[str]:
    """
    Get Python version from MAP_VERSION_TO_INSTALL constants.
    
    Args:
        repo: Repository name (e.g. "matplotlib/matplotlib")
        instance_version: Repository version (e.g. "1.2") - NOT the python version
        
    Returns:
        Python version as string (e.g. "3.9") or None if not found
    """
    from .dataset_constants import MAP_VERSION_TO_INSTALL
    
    if repo not in MAP_VERSION_TO_INSTALL:
        return "3.9"
        
    version_map = MAP_VERSION_TO_INSTALL[repo]
    if instance_version not in version_map:
        return "3.9"
        
    return version_map[instance_version].get("python", "3.9")


def uv_venv(repo_dir: Path, repo_name: str, repo_version: str, force_venv: bool = False) -> None:
    """Create a virtual environment using uv."""
    venv_path = repo_dir / ".venv"
    if venv_path.exists() and not force_venv:
        logging.info(f"Virtual environment already exists at {venv_path}")
        return

    # Temporarily unset VIRTUAL_ENV to avoid interference
    old_venv = os.environ.pop("VIRTUAL_ENV", None)
    print(f"repo_dir={repo_dir}")
    try:
        cmd = [
            "uv",
            "venv",
            "--seed",
            "--no-project",
            "--directory",
            str(repo_dir),
            "--project",
            str(repo_dir),
        ]

        # Get Python version from constants
        python_version = get_python_version(repo_name, repo_version)
        print(f"python_version from constants={python_version}")
        if python_version:
            python_cmd = f"python{python_version}"
            logging.info(f"Using Python version {python_version} for {repo_name} version {repo_version}")
            cmd.extend(["--python", python_cmd])

        cmd.append(str(repo_dir / ".venv"))
        subprocess.run(cmd, check=True)
    finally:
        if old_venv:
            os.environ["VIRTUAL_ENV"] = old_venv


# Not working as expected due to:
# error: No `project` table found in: `.../pyproject.toml`
def uv_sync(repo_dir: Path, python_path: Path) -> None:
    """Sync dependencies using uv."""
    cmd = [
        "uv",
        "sync",
        "--directory",
        str(repo_dir),
        "--project",
        str(repo_dir),
        "--python",
        str(python_path),
    ]
    subprocess.run(cmd, cwd=str(repo_dir), check=True)


def uv_pip_install(repo_dir: Path, args: List[str]) -> None:
    """Run uv pip install with given arguments."""
    venv_path = repo_dir / ".venv"
    python_path = venv_path / "bin" / "python"

    cmd = (
        [
            "uv",
            "pip",
            # "--no-config",
            "--directory",
            str(repo_dir),
            "--project",
            str(repo_dir),
            "install",
        ]
        + args
        + ["--python", str(python_path)]
    )
    subprocess.run(cmd, cwd=str(repo_dir), check=True)


def setup_venv_and_deps(repo_dir: Path, repo_name: str, repo_version: str, force_venv: bool) -> None:
    """
    Setup virtual environment and install dependencies:
    - uv venv .venv --seed
    - If pyproject.toml -> uv pip install .
    - If requirements.txt -> uv pip install -r requirements.txt
    - If requirements-dev.txt -> uv pip install -r requirements-dev.txt
    - If there's a setup.py or pyproject => uv pip install -e .
    """

    with change_directory(repo_dir):
        uv_venv(repo_dir, repo_name, repo_version, force_venv)

        # Deprecated below, should be handled by --seed above
        # uv_pip_install(repo_dir, ["--upgrade", "pip"])
        # uv_pip_install(repo_dir, ["--upgrade", "setuptools", "wheel"])

        # 1) optional pyproject
        pyproject_path = repo_dir / "pyproject.toml"
        if pyproject_path.is_file():
            uv_pip_install(repo_dir, ["."])

        # 2) optional requirements.txt
        req_file = repo_dir / "requirements.txt"
        if req_file.is_file():
            uv_pip_install(repo_dir, ["-r", "requirements.txt"])

        # 3) optional requirements-dev.txt
        req_dev_file = repo_dir / "requirements-dev.txt"
        if req_dev_file.is_file():
            uv_pip_install(repo_dir, ["-r", "requirements-dev.txt"])

        # 4) install the cloned project in editable mode if it's a Python package
        setup_path = repo_dir / "setup.py"
        if pyproject_path.is_file() or setup_path.is_file():
            logging.info("Installing cloned project in editable mode.")
            uv_pip_install(repo_dir, ["-e", "."])
