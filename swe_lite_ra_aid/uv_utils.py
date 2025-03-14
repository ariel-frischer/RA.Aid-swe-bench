"""Module for handling UV virtual environment setup and package installation."""

import os
from pathlib import Path
import logging
import subprocess
from typing import Optional

from .io_utils import change_directory
from .logger import logger


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
    logger.debug(f"repo_dir={repo_dir}")
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
        logger.debug(f"python_version from constants={python_version}")

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
            logger.debug(result.stdout)
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
    logger.debug("\nSETUP_UV_VENV:")
    logger.debug(f"repo_dir: {repo_dir}")
    logger.debug(f"repo_name: {repo_name}")
    logger.debug(f"repo_version: {repo_version}")
    logger.debug(f"force_venv: {force_venv}")
    
    venv_path = repo_dir / ".venv"
    logger.debug(f"venv_path: {venv_path}")
    
    if venv_path.exists() and not force_venv:
        logger.info(f"Virtual environment already exists at {venv_path}")
        return

    logger.debug("\nRemoving VIRTUAL_ENV from environment")
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
        logger.debug(f"Using Python version: {python_version}")
        cmd.extend(["--python", python_version])

        logger.debug(f"\nRunning UV command: {' '.join(cmd + [str(venv_path)])}")
        try:
            result = subprocess.run(
                cmd + [str(venv_path)], check=True, capture_output=True, text=True
            )
            logger.debug("\nUV command output:")
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"UV venv creation failed with exit code {e.returncode}\n"
                f"Command: {' '.join(cmd)}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            logger.error(f"\nERROR: {error_msg}")
            raise RuntimeError(error_msg) from e

    finally:
        if old_venv:
            logger.debug(f"\nRestoring VIRTUAL_ENV: {old_venv}")
            os.environ["VIRTUAL_ENV"] = old_venv


def setup_legacy_venv(repo_dir: Path, python_version: str) -> None:
    """Setup virtual environment using venv + pip for Python <3.7"""
    venv_path = repo_dir / ".venv"

    try:
        # Get pyenv root and initialize it properly
        pyenv_root = subprocess.run(
            ["pyenv", "root"],
            check=True,
            capture_output=True,
            text=True
        ).stdout.strip()

        # Create shell script with proper pyenv initialization
        shell_script = f"""
            export PYENV_ROOT="{pyenv_root}"
            export PATH="$PYENV_ROOT/bin:$PATH"
            eval "$(pyenv init -)"
            eval "$(pyenv init --path)"
            
            # Use Python 3.6.15 to create venv
            python_path="{pyenv_root}/versions/3.6.15/bin/python"
            if [ ! -f "$python_path" ]; then
                echo "Python 3.6.15 not found at $python_path"
                exit 1
            fi
            
            "$python_path" -m venv "{venv_path}"
        """
        
        # Execute the shell script
        subprocess.run(["bash", "-c", shell_script], check=True)

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
        pass  # No need to reset pyenv shell since we're not using it


def setup_venv_and_deps(
    repo_dir: Path, repo_name: str, repo_version: str, force_venv: bool
) -> None:
    """
    Setup virtual environment and install dependencies using either:
    - uv for Python >=3.7
    - venv + pip for Python <3.7
    """
    logger.debug("\nSETUP_VENV_AND_DEPS:")
    logger.debug(f"repo_dir: {repo_dir}")
    logger.debug(f"repo_name: {repo_name}")
    logger.debug(f"repo_version: {repo_version}")
    logger.debug(f"force_venv: {force_venv}")

    with change_directory(repo_dir):
        logger.debug(f"\nChanged directory to: {os.getcwd()}")
        
        python_version = get_python_version(repo_name, repo_version)
        logger.info(f"Hardcoded python_version from constants.py: {python_version}")

        # Parse version to compare
        major, minor = map(int, python_version.split(".")[:2])
        logger.debug(f"Parsed version: Python {major}.{minor}")

        if major == 3 and minor < 7:
            logger.debug("\nUsing legacy venv setup (Python < 3.7)")
            setup_legacy_venv(repo_dir, python_version)
        else:
            logger.debug("\nUsing uv venv setup (Python >= 3.7)")
            setup_uv_venv(repo_dir, repo_name, repo_version, force_venv)

