from git import Repo

def diff_versus_commit(git_dname, commit):
    """
    Take a diff of `git_dname` current contents versus the `commit`.
    """
    repo = Repo(git_dname)
    try:
        # Get detailed diff with color and full context
        diff = repo.git.diff(
            commit,
            color="always",  # Force color output even when piped
            unified=1000,    # Show full file context
            ignore_space_at_eol=True,
            ignore_blank_lines=True
        )
        # Also show staged changes
        staged_diff = repo.git.diff(
            "--cached",
            color="always",
            unified=1000,
            ignore_space_at_eol=True,
            ignore_blank_lines=True
        )
        return f"Working tree changes:\n{diff}\n\nStaged changes:\n{staged_diff}"
    except Exception as e:
        return f"Error getting diff: {str(e)}"


def files_in_patch(patch):
    """
    Extract the list of modified files from a unified diff patch string.
    """
    files = []
    for line in patch.split("\n"):
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            fname = line.split("/", 1)[1]
            if fname not in files:
                files.append(fname)
    return files


def checkout_repo_url_commit(git_tempdir, repo_url, commit):
    """
    Clone the git repo from url into tempdir at specific commit.
    """
    repo = Repo.clone_from(repo_url, git_tempdir)
    repo.git.checkout(commit)
    return repo

def checkout_repo(git_tempdir, entry):
    """
    Clone the SWE Bench entry's git `repo` into `dname` at the `base_commit`.
    Make a tempdir if no `dname` provided.
    """
    github_url = "https://github.com/"
    repo_url = github_url + entry["repo"]
    commit = entry["base_commit"]

    print(f"Cloning {repo_url} at commit {commit}")
    return checkout_repo_url_commit(git_tempdir, repo_url, commit)
