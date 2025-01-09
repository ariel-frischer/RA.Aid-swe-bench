import logging
import subprocess
from pathlib import Path
from git import Repo
from typing import Optional


def get_git_patch(repo_dir: Path) -> Optional[str]:
    """Get the current git diff as a patch string."""
    try:
        result = subprocess.run(
            ["git", "diff"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout if result.stdout else None
    except subprocess.CalledProcessError:
        logging.error("Failed to get git diff")
        return None


def uv_run_raaid(repo_dir: Path, prompt: str) -> Optional[str]:
    """
    Call 'uv run ra-aid' with the given prompt in the environment,
    streaming output directly to the console (capture_output=False).
    Returns the patch if successful, else None.
    """
    cmd = [
        "uv", "run", "ra-aid",
        "--cowboy-mode",
        "-m", prompt
    ]
    # We are NOT capturing output, so it streams live:
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_dir,
            text=True,
            check=False,   # We manually handle exit code
        )
        if result.returncode != 0:
            logging.error("ra-aid returned non-zero exit code.")
            return None
    except subprocess.TimeoutExpired:
        logging.error("ra-aid timed out")
        return None
    except Exception as e:
        logging.error(f"ra-aid error: {e}")
        return None

    # Collect patch
    patch = get_git_patch(repo_dir)
    return patch


def diff_versus_commit(git_dname, commit) -> str:
    repo = Repo(git_dname)
    return repo.git.diff(commit)

def files_in_patch(patch):
    files = []
    for line in patch.split("\n"):
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            fname = line.split("/", 1)[1]
            if fname not in files:
                files.append(fname)
    return files


def checkout_repo_url_commit(git_tempdir, repo_url, commit):
    repo = Repo.clone_from(repo_url, git_tempdir)
    repo.git.checkout(commit)
    return repo


def checkout_repo(git_tempdir, entry):
    github_url = "https://github.com/"
    repo_url = github_url + entry["repo"]
    setup_commit = entry["environment_setup_commit"]

    print(f"Cloning {repo_url} at environment setup commit {setup_commit}")
    return checkout_repo_url_commit(git_tempdir, repo_url, setup_commit)
