"""Module for managing git repositories and worktrees."""

import os
import shutil
import subprocess
from pathlib import Path
from git import Repo, exc as git_exc
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
        
        # Create venvs directory for storing virtual environments
        self.venvs_root = self.cache_root / "venvs"
        self.venvs_root.mkdir(parents=True, exist_ok=True)
        print(f"Virtual environments will be stored in: {self.venvs_root}")

        self.ra_aid_version = self._detect_ra_aid_version()
        print(f"ra_aid_version={self.ra_aid_version}")

    def get_venv_path(self, repo_name: str, setup_commit: str) -> Path:
        """Get path to cached virtual environment directory."""
        safe_name = repo_name.replace("/", "_")
        venv_dir = self.venvs_root / f"{safe_name}_{setup_commit}"
        return venv_dir

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

    def ensure_venv(self, repo_name: str, setup_commit: str, version: str, cache_path: Path) -> None:
        """
        Ensure virtual environment exists and is set up with dependencies.
        
        Args:
            repo_name: Repository name (e.g. "matplotlib/matplotlib")
            setup_commit: Commit hash for environment setup
            version: Repository version for Python version detection
            cache_path: Path to cached repository
        """
        venv_path = self.get_venv_path(repo_name, setup_commit)
        print("\nENSURE_VENV:")
        print(f"repo_name: {repo_name}")
        print(f"setup_commit: {setup_commit}")
        print(f"version: {version}")
        print(f"cache_path: {cache_path}")
        print(f"venv_path: {venv_path}")

        if not (venv_path / ".venv").exists():
            print("\nSetting up new virtual environment:")
            print(f"venv_path: {venv_path}")
            venv_path.mkdir(parents=True, exist_ok=True)
            
            print("\nCopying repo contents to venv directory...")
            import shutil
            for item in cache_path.iterdir():
                if item.name != ".git":
                    dest = venv_path / item.name
                    print(f"Copying {item} -> {dest}")
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)
            
            from .uv_utils import setup_venv_and_deps
            print("\nCalling setup_venv_and_deps...")
            setup_venv_and_deps(venv_path, repo_name, version, force_venv=True)
        else:
            print(f"\nUsing cached virtual environment at {venv_path}")

    def ensure_base_repo(self, repo_url: str, setup_commit: str, version: str) -> Tuple[Repo, Path]:
        """
        Ensure base repository exists in cache.

        Args:
            repo_url: GitHub repository URL
            setup_commit: Commit hash for environment setup
            version: Repository version for Python version detection

        Returns:
            Tuple of (Repo object, Path to cached repo)
        """
        print(f"\nEnsuring base repo exists for URL: {repo_url}")
        print(f"Setup commit: {setup_commit}")

        repo_name = repo_url.split("github.com/")[-1]
        print(f"Extracted repo name: {repo_name}")

        cache_path = self.get_cached_repo_path(repo_name)

        # Ensure parent directories exist
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if cache_path.exists():
                print(f"Using cached repo at {cache_path}")
                try:
                    # Validate the cached repo
                    repo = Repo(cache_path)
                    # Test git operations to ensure repo is valid
                    repo.git.rev_parse("--git-dir")
                    print("Cached repository is valid")
                except Exception as e:
                    print(f"Cached repository is invalid: {e}")
                    print("Removing corrupted cache and trying fresh clone")
                    shutil.rmtree(cache_path)
                    cache_path.mkdir(parents=True, exist_ok=True)
                    repo = Repo.clone_from(repo_url, str(cache_path))
            else:
                cache_path.mkdir(parents=True, exist_ok=True)
                print(f"Cloning {repo_url} to cache at {cache_path}")
                repo = Repo.clone_from(repo_url, str(cache_path))

            # Checkout correct commit
            repo.git.checkout(setup_commit)

            # Ensure virtual environment is set up
            self.ensure_venv(repo_name, setup_commit, version, cache_path)

            return repo, cache_path

        except Exception as e:
            logging.error(
                f"Failed to ensure base repo exists at {cache_path}: {str(e)}"
            )
            error_msg = ""
            if isinstance(e, git_exc.GitCommandError):
                error_msg = f"Git command failed: {e.command}\nStatus: {e.status}\nStdout: {e.stdout}\nStderr: {e.stderr}"
            elif "Repo" in str(type(e)):
                error_msg = f"Git repository operation failed: {str(e)}"
            else:
                error_msg = f"Error type: {type(e).__name__}\nDetails: {str(e)}"

            logging.error(f"Failed to setup repository at {cache_path}:\n{error_msg}")
            
            # Clean up any partial clone
            if cache_path.exists():
                try:
                    shutil.rmtree(cache_path)
                except Exception as cleanup_err:
                    logging.error(f"Failed to cleanup {cache_path}: {cleanup_err}")

            raise RuntimeError(f"Repository setup failed: {error_msg}") from e

    def create_venv_symlink(self, base_repo: Repo, worktree_path: Path, base_commit: str) -> Path:
        """
        Create symlink to cached virtual environment in worktree.

        Args:
            base_repo: Base repository object
            worktree_path: Path to worktree directory
            base_commit: Commit hash being used

        Returns:
            Path to the virtual environment that was linked
        """
        repo_name = Path(base_repo.working_dir).name.replace("__", "/")
        venv_path = self.get_venv_path(repo_name, base_commit) / ".venv"
        print(f"Linking to cached venv at: {venv_path}")
        worktree_venv = worktree_path / ".venv"

        try:
            os.symlink(venv_path, worktree_venv)
        except OSError as e:
            logging.warning(f"Failed to create symlink to cached venv: {e}")
            raise

        return venv_path

    def create_worktree(self, base_repo: Repo, base_commit: str, setup_commit: str) -> Tuple[Path, Path]:
        """
        Create new worktree for given commit with symlinked .venv

        Args:
            base_repo: Base repository object
            base_commit: Commit hash to checkout
            setup_commit: Commit hash for environment setup

        Returns:
            Tuple of (worktree path, symlink target path)
        """
        # Create unique worktree name
        worktree_name = (
            f"worktree-{base_commit}-{tempfile.mktemp(dir='').split('/')[-1]}"
        )
        worktree_path = Path(base_repo.working_dir).parent / worktree_name

        base_repo.git.worktree("add", str(worktree_path), base_commit)

        # Create symlink to cached virtual environment using setup_commit
        venv_path = self.create_venv_symlink(base_repo, worktree_path, setup_commit)

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
