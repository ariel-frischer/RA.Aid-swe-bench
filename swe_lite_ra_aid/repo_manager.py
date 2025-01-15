"""Module for managing git repositories and worktrees."""

import os
import shutil
import subprocess
from pathlib import Path
from git import Repo
import tempfile
from typing import Tuple
import logging


class RepoManager:
    def __init__(self, cache_root: Path):
        """
        Initialize RepoManager with root directory for cached repos.

        Args:
            cache_root: Root directory where cached repositories will be stored.
                       Should be an absolute path to project_root/repos/
        """
        self.cache_root = Path(cache_root).resolve()
        print(f"Initializing RepoManager with cache root: {self.cache_root}")
        self.cache_root.mkdir(parents=True, exist_ok=True)

        self.ra_aid_version = self._detect_ra_aid_version()
        print(f"ra_aid_version={self.ra_aid_version}")

    def _detect_ra_aid_version(self) -> str:
        """Detect installed ra-aid version."""
        from .config import DEFAULT_RA_AID_VERSION

        try:
            result = subprocess.run(
                ["ra-aid", "--version"], capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except Exception as e:
            logging.warning(f"Failed to detect ra-aid version: {e}")
            return DEFAULT_RA_AID_VERSION

    def get_cached_repo_path(self, repo_name: str) -> Path:
        """Get path where cached repo should be stored."""
        print(f"\nGetting cached path for repo: {repo_name}")

        # Extract owner/repo part from full URL if needed
        if "github.com/" in repo_name:
            repo_name = repo_name.split("github.com/")[-1]
            print(f"Extracted from URL: {repo_name}")

        # Handle both https and git protocols
        repo_name = repo_name.replace("https://", "").replace("git://", "")

        # Convert owner/repo to owner__repo format
        safe_name = repo_name.replace("/", "__")
        cache_path = self.cache_root / safe_name

        print(f"Converted to safe name: {safe_name}")
        # print(f"Full cache path: {cache_path}")

        return cache_path

    def ensure_base_repo(self, repo_url: str, setup_commit: str) -> Tuple[Repo, Path]:
        """
        Ensure base repository exists in cache with dependencies installed.

        Args:
            repo_url: GitHub repository URL
            setup_commit: Commit hash for environment setup

        Returns:
            Tuple of (Repo object, Path to cached repo)
        """
        print(f"\nEnsuring base repo exists for URL: {repo_url}")
        print(f"Setup commit: {setup_commit}")

        repo_name = repo_url.split("github.com/")[-1]
        print(f"Extracted repo name: {repo_name}")

        cache_path = self.get_cached_repo_path(repo_name)
        # print(f"Cache path resolved to: {cache_path}")

        # Ensure parent directories exist
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if not cache_path.exists():
                cache_path.mkdir(parents=True, exist_ok=True)

                # Clone fresh repo
                print(f"Cloning {repo_url} to cache at {cache_path}")
                repo = Repo.clone_from(
                    repo_url, str(cache_path)
                )  # Convert Path to str for git
                repo.git.checkout(setup_commit)

                # Setup virtual environment in cached repo
                from .uv_utils import setup_venv_and_deps

                # Get version from task instance
                version = task["version"]
                setup_venv_and_deps(cache_path, repo_name, version, force_venv=True)
            else:
                print(f"Using cached repo at {cache_path}")
                repo = Repo(cache_path)

            return repo, cache_path

        except Exception as e:
            logging.error(
                f"Failed to ensure base repo exists at {cache_path}: {str(e)}"
            )
            # Clean up any partial clone
            if cache_path.exists():
                shutil.rmtree(cache_path)
            # Re-raise with more context
            raise RuntimeError(
                f"Failed to setup repository at {cache_path}: {str(e)}"
            ) from e

    def create_worktree(self, base_repo: Repo, base_commit: str) -> Tuple[Path, Path]:
        """
        Create new worktree for given commit with symlinked .venv

        Args:
            base_repo: Base repository object
            base_commit: Commit hash to checkout

        Returns:
            Tuple of (worktree path, symlink target path)
        """
        # Create unique worktree name
        worktree_name = (
            f"worktree-{base_commit}-{tempfile.mktemp(dir='').split('/')[-1]}"
        )
        worktree_path = Path(base_repo.working_dir).parent / worktree_name

        base_repo.git.worktree("add", str(worktree_path), base_commit)

        # Create symlink to .venv
        venv_path = Path(base_repo.working_dir) / ".venv"
        print(f"venv_path={venv_path}")
        worktree_venv = worktree_path / ".venv"

        try:
            os.symlink(venv_path, worktree_venv)
        except OSError as e:
            logging.warning(f"Failed to create symlink, copying .venv instead: {e}")
            shutil.copytree(venv_path, worktree_venv)

        return worktree_path, venv_path

    def cleanup_worktree(self, repo: Repo, worktree_path: Path):
        """
        Remove worktree and its directory

        Args:
            repo: Repository object
            worktree_path: Path to worktree to remove
        """
        # try:
        #     repo.git.worktree('remove', str(worktree_path), force=True)
        # except Exception as e:
        #     logging.error(f"Error removing worktree: {e}")

        try:
            shutil.rmtree(worktree_path)
        except Exception as e:
            logging.error(f"Error removing worktree directory: {e}")
