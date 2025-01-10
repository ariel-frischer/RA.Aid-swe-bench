from git import Repo


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


def stage_and_get_patch(worktree_path: str) -> str:
    """Stage all changes and generate a patch against HEAD."""
    repo = Repo(worktree_path)
    # Add all files except .venv directory because .venv is symbolinked, will be edited everytime
    repo.git.add('.')  # Stage all tracked files
    repo.git.add('*')  # Stage new files
    repo.git.reset('HEAD', '.venv', '--')  # Unstage .venv directory if it was staged
    return repo.git.diff('HEAD')
