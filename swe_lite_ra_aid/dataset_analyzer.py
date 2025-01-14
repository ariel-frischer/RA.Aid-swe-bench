"""Analyze SWE-bench Lite dataset for unique setup commits per repository."""

from collections import defaultdict
from datasets import load_dataset
from typing import Dict, Set


def analyze_setup_commits():
    """Analyze unique setup commits for each repository in the dataset."""
    # Load the dataset
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    # Dictionary to store repo -> set of setup commits
    repo_setup_commits: Dict[str, Set[str]] = defaultdict(set)
    
    # Collect setup commits per repo
    for instance in dataset:
        repo = instance["repo"]
        setup_commit = instance["environment_setup_commit"]
        repo_setup_commits[repo].add(setup_commit)
    
    # Print analysis
    print("\nRepository Setup Commit Analysis:")
    print("=" * 80)
    
    # Sort repos by number of unique setup commits (descending)
    sorted_repos = sorted(
        repo_setup_commits.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )
    
    for repo, setup_commits in sorted_repos:
        num_commits = len(setup_commits)
        print(f"\nRepository: {repo}")
        print(f"Number of unique setup commits: {num_commits}")
        print("Setup commits:")
        for commit in sorted(setup_commits):
            print(f"  - {commit}")
    
    # Print summary
    print("\nSummary:")
    print("=" * 80)
    print(f"Total repositories: {len(repo_setup_commits)}")
    print(f"Repositories with multiple setup commits: "
          f"{sum(1 for commits in repo_setup_commits.values() if len(commits) > 1)}")
    print(f"Repositories with single setup commit: "
          f"{sum(1 for commits in repo_setup_commits.values() if len(commits) == 1)}")


if __name__ == "__main__":
    analyze_setup_commits()
