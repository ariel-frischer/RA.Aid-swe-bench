"""Module for handling UV virtual environment setup and package installation."""

import os
import re
from pathlib import Path
import logging
import subprocess
from typing import List, Optional
from configparser import ConfigParser
from .io_utils import change_directory


def detect_python_version(repo_dir: Path) -> Optional[str]:
    """
    Detect required Python version from various configuration files.
    Returns the Python version as a string (e.g. "3.11") or None if not specified.
    """
    def parse_version_constraint(text: str) -> Optional[str]:
        """Extract version from constraints like '>=3.8,<3.12' or '>=3.8'"""
        match = re.search(r'>=\s*([\d.]+)', text)
        return match.group(1) if match else None

    def parse_toml(path: Path) -> Optional[str]:
        """Simple TOML parser for Python version requirements"""
        try:
            with open(path) as f:
                content = f.read()
                # Look for requires-python in project section
                match = re.search(r'requires-python\s*=\s*[\'"]([^"\']+)[\'"]', content)
                if match:
                    return parse_version_constraint(match.group(1))
        except Exception as e:
            logging.warning(f"Error parsing {path}: {e}")
        return None

    # Check pyproject.toml first (PEP 518)
    pyproject_path = repo_dir / "pyproject.toml"
    if pyproject_path.exists():
        version = parse_toml(pyproject_path)
        if version:
            return version

    # Check setup.py
    setup_path = repo_dir / "setup.py"
    if setup_path.exists():
        try:
            with open(setup_path) as f:
                content = f.read()
                match = re.search(r'python_requires\s*=\s*[\'"]([^"\']+)[\'"]', content)
                if match:
                    return parse_version_constraint(match.group(1))
        except Exception as e:
            logging.warning(f"Error parsing setup.py: {e}")

    # Check requirements.txt
    req_path = repo_dir / "requirements.txt"
    if req_path.exists():
        try:
            with open(req_path) as f:
                for line in f:
                    if "python_version" in line:
                        return parse_version_constraint(line)
        except Exception as e:
            logging.warning(f"Error parsing requirements.txt: {e}")

    # Check tox.ini
    tox_path = repo_dir / "tox.ini"
    if tox_path.exists():
        try:
            config = ConfigParser()
            config.read(tox_path)
            if "tox" in config:
                version = config["tox"].get("min_version")
                if version:
                    return version
        except Exception as e:
            logging.warning(f"Error parsing tox.ini: {e}")

    # Default fallback versions for known repos
    repo_defaults = {
        "matplotlib": "3.11",  # matplotlib currently has issues with 3.12
    }
    
    repo_name = repo_dir.name.replace("__", "/")
    return repo_defaults.get(repo_name.split("/")[-1])

def uv_venv(repo_dir: Path, repo_name: str, force_venv: bool = False) -> None:
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
        
        # Detect and use specific Python version if available
        python_version = detect_python_version(repo_dir)
        if python_version:
            python_cmd = f"python{python_version}"
            logging.info(f"Using Python version {python_version} for {repo_name}")
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


def setup_venv_and_deps(repo_dir: Path, repo_name: str, force_venv: bool) -> None:
    """
    Setup virtual environment and install dependencies:
    - uv venv .venv --seed
    - If pyproject.toml -> uv pip install .
    - If requirements.txt -> uv pip install -r requirements.txt
    - If requirements-dev.txt -> uv pip install -r requirements-dev.txt
    - If there's a setup.py or pyproject => uv pip install -e .
    """

    with change_directory(repo_dir):
        uv_venv(repo_dir, repo_name, force_venv)

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
