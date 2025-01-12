"""Module for handling UV virtual environment setup and package installation."""

from pathlib import Path
import logging
import subprocess
from typing import List
from .io_utils import change_directory

def uv_venv(repo_dir: Path, repo_name: str, force_venv: bool = False) -> None:
    """Create a virtual environment using uv."""
    venv_path = repo_dir / ".venv"
    if venv_path.exists() and not force_venv:
        logging.info(f"Virtual environment already exists at {venv_path}")
        return

    cmd = ["uv", "venv", ".venv"]
    subprocess.run(cmd, cwd=repo_dir, check=True)

def uv_pip_install(repo_dir: Path, args: List[str]) -> None:
    """Run uv pip install with given arguments."""
    cmd = ["uv", "pip", "install"] + args
    subprocess.run(cmd, cwd=repo_dir, check=True)

def setup_venv_and_deps(repo_dir: Path, repo_name: str, force_venv: bool) -> None:
    """
    Setup virtual environment and install dependencies:
    - uv venv .venv --python=xxx (optional)
    - uv pip install --upgrade pip
    - uv pip install --upgrade setuptools wheel  (so pkg_resources etc. are available)
    - If pyproject.toml -> uv pip install .
    - If requirements.txt -> uv pip install -r requirements.txt
    - If requirements-dev.txt -> uv pip install -r requirements-dev.txt
    - If there's a setup.py or pyproject => uv pip install -e .
    """
    with change_directory(repo_dir):
        uv_venv(repo_dir, repo_name, force_venv)

        # 1) upgrade pip
        uv_pip_install(repo_dir, ["--upgrade", "pip"])

        # 2) ensure setuptools & wheel are installed/up to date
        uv_pip_install(repo_dir, ["--upgrade", "setuptools", "wheel"])

        # 3) optional pyproject
        pyproject_path = repo_dir / "pyproject.toml"
        if pyproject_path.is_file():
            uv_pip_install(repo_dir, ["."])

        # 4) optional requirements.txt
        req_file = repo_dir / "requirements.txt"
        if req_file.is_file():
            uv_pip_install(repo_dir, ["-r", "requirements.txt"])

        # 5) optional requirements-dev.txt
        req_dev_file = repo_dir / "requirements-dev.txt"
        if req_dev_file.is_file():
            uv_pip_install(repo_dir, ["-r", "requirements-dev.txt"])

        # 6) install the cloned project in editable mode if it's a Python package
        setup_path = repo_dir / "setup.py"
        if pyproject_path.is_file() or setup_path.is_file():
            logging.info("Installing cloned project in editable mode.")
            uv_pip_install(repo_dir, ["-e", "."])
