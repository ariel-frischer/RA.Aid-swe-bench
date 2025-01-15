"""Module for handling UV virtual environment setup and package installation."""

import os
from pathlib import Path
import logging
import subprocess
from typing import Optional

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


def uv_venv(
    repo_dir: Path, repo_name: str, repo_version: str, force_venv: bool = False
) -> None:
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

        # Try specified Python version first
        if python_version:
            # Just pass the version to uv and let it handle finding Python
            cmd.extend(["--python", python_version])
            logging.info(
                f"Using Python version {python_version} for {repo_name} version {repo_version}"
            )

        cmd.append(str(repo_dir / ".venv"))

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"UV venv creation failed with exit code {e.returncode}\n"
                f"Command: {' '.join(cmd)}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            logging.error(error_msg)
            raise RuntimeError(error_msg) from e
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


def setup_uv_venv(
    repo_dir: Path, repo_name: str, repo_version: str, force_venv: bool
) -> None:
    """Setup virtual environment using uv for Python >=3.7"""
    venv_path = repo_dir / ".venv"
    if venv_path.exists() and not force_venv:
        logging.info(f"Virtual environment already exists at {venv_path}")
        return

    old_venv = os.environ.pop("VIRTUAL_ENV", None)
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

        python_version = get_python_version(repo_name, repo_version)
        cmd.extend(["--python", python_version])

        try:
            result = subprocess.run(
                cmd + [str(venv_path)], check=True, capture_output=True, text=True
            )
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"UV venv creation failed with exit code {e.returncode}\n"
                f"Command: {' '.join(cmd)}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            logging.error(error_msg)
            raise RuntimeError(error_msg) from e

    finally:
        if old_venv:
            os.environ["VIRTUAL_ENV"] = old_venv


def setup_legacy_venv(repo_dir: Path, python_version: str) -> None:
    """Setup virtual environment using venv + pip for Python <3.7"""
    venv_path = repo_dir / ".venv"

    try:
        # Get pyenv root and construct path to Python 3.6.15
        pyenv_root = subprocess.run(
            ["pyenv", "root"],
            check=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        
        python_path = Path(pyenv_root) / "versions" / "3.6.15" / "bin" / "python"
        
        if not python_path.exists():
            raise RuntimeError(f"Python 3.6.15 not found at {python_path}")

        # Use the full Python path directly
        subprocess.run(
            [str(python_path), "-m", "venv", str(venv_path)],
            check=True
        )

        pip_path = venv_path / "bin" / "pip"
        subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip", "setuptools", "wheel"],
            check=True,
        )

        # Install dependencies similar to uv logic
        if (repo_dir / "pyproject.toml").is_file():
            subprocess.run([str(pip_path), "install", "."], check=True)

        if (repo_dir / "requirements.txt").is_file():
            subprocess.run(
                [str(pip_path), "install", "-r", "requirements.txt"], check=True
            )

        if (repo_dir / "requirements-dev.txt").is_file():
            subprocess.run(
                [str(pip_path), "install", "-r", "requirements-dev.txt"], check=True
            )

        # Install in editable mode if it's a Python package
        if (repo_dir / "setup.py").is_file() or (repo_dir / "pyproject.toml").is_file():
            logging.info("Installing cloned project in editable mode.")
            subprocess.run([str(pip_path), "install", "-e", "."], check=True)

    except subprocess.CalledProcessError as e:
        error_msg = (
            f"Legacy venv setup failed with exit code {e.returncode}\n"
            f"Command: {e.args}\n"
            f"Stdout: {e.stdout if hasattr(e, 'stdout') else ''}\n"
            f"Stderr: {e.stderr if hasattr(e, 'stderr') else ''}"
        )
        logging.error(error_msg)
        raise RuntimeError(error_msg) from e
    finally:
        # Reset pyenv shell to whatever it was before
        subprocess.run(["pyenv", "shell", "--unset"], check=True)


def setup_venv_and_deps(
    repo_dir: Path, repo_name: str, repo_version: str, force_venv: bool
) -> None:
    """
    Setup virtual environment and install dependencies using either:
    - uv for Python >=3.7
    - venv + pip for Python <3.7
    """
    with change_directory(repo_dir):
        python_version = get_python_version(repo_name, repo_version)
        print(f"python_version from constants={python_version}")

        # Parse version to compare
        major, minor = map(int, python_version.split(".")[:2])

        if major == 3 and minor < 7:
            setup_legacy_venv(repo_dir, python_version)
        else:
            setup_uv_venv(repo_dir, repo_name, repo_version, force_venv)

