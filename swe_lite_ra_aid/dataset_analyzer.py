"""Analyze SWE-bench Lite dataset for unique setup commits and Python versions per repository."""

import shutil
import tempfile
from collections import defaultdict
from datasets import load_dataset
from git import Repo
from pathlib import Path
from typing import Dict, Set, Tuple
from .uv_utils import detect_python_version


def clone_and_analyze_repo(repo_url: str, setup_commits: Set[str], temp_dir: Path) -> Tuple[Set[str], Dict[str, str]]:
    """Clone a repository and analyze Python versions for each setup commit."""
    python_versions = set()
    commit_versions = {}  # Map commits to their detected Python versions
    
    repo_name = repo_url.split("/")[-1]
    repo_path = temp_dir / repo_name
    
    print(f"\nCloning {repo_url} to analyze {len(setup_commits)} setup commits...")
    try:
        # Clone the repository
        repo = Repo.clone_from(f"https://github.com/{repo_url}", str(repo_path))
        
        # Check each setup commit
        for setup_commit in sorted(setup_commits):
            print(f"\nChecking setup commit: {setup_commit}")
            try:
                repo.git.checkout(setup_commit)
                python_version = detect_python_version(repo_path)
                if python_version:
                    python_versions.add(python_version)
                    commit_versions[setup_commit] = python_version
                    print(f"Found Python {python_version} for commit {setup_commit}")
            except Exception as e:
                print(f"Error checking commit {setup_commit}: {e}")
                
    except Exception as e:
        print(f"Error cloning/analyzing repo {repo_url}: {e}")
    finally:
        # Cleanup
        if repo_path.exists():
            shutil.rmtree(repo_path)
            
    return python_versions, commit_versions


def analyze_setup_commits():
    """Analyze unique setup commits + python versions for each repository in the dataset."""
    # Load the dataset
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    # Dictionaries to store repo data
    repo_setup_commits: Dict[str, Set[str]] = defaultdict(set)
    repo_python_versions: Dict[str, Set[str]] = defaultdict(set)
    repo_commit_versions: Dict[str, Dict[str, str]] = defaultdict(dict)

    # First pass: collect all setup commits per repo
    for instance in dataset:
        repo = instance["repo"]
        setup_commit = instance["environment_setup_commit"]
        repo_setup_commits[repo].add(setup_commit)

    # Create temp directory for repo analysis
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Second pass: clone each repo once and analyze all its commits
        for repo, setup_commits in repo_setup_commits.items():
            versions, commit_versions = clone_and_analyze_repo(repo, setup_commits, temp_path)
            repo_python_versions[repo].update(versions)
            repo_commit_versions[repo].update(commit_versions)

    # Print analysis
    print("\nRepository Setup Commit Analysis:")
    print("=" * 80)

    # Sort repos by number of unique setup commits (descending)
    sorted_repos = sorted(
        repo_setup_commits.items(), key=lambda x: len(x[1]), reverse=True
    )

    for repo, setup_commits in sorted_repos:
        num_commits = len(setup_commits)
        python_versions = (
            sorted(repo_python_versions[repo]) if repo in repo_python_versions else []
        )
        commit_versions = repo_commit_versions[repo]

        print(f"\nRepository: {repo}")
        print(f"Number of unique setup commits: {num_commits}")
        print("Setup commits and their Python versions:")
        for commit in sorted(setup_commits):
            version = commit_versions.get(commit, "unknown")
            print(f"  - {commit}: Python {version}")

        print(f"Unique Python versions detected: {len(python_versions)}")
        for version in python_versions:
            print(f"  - Python {version}")

    # Print summary
    print("\nSummary:")
    print("=" * 80)
    print(f"Total repositories: {len(repo_setup_commits)}")
    print(
        f"Repositories with multiple setup commits: "
        f"{sum(1 for commits in repo_setup_commits.values() if len(commits) > 1)}"
    )
    print(
        f"Repositories with single setup commit: "
        f"{sum(1 for commits in repo_setup_commits.values() if len(commits) == 1)}"
    )
    print(f"Repositories with Python version detected: {len(repo_python_versions)}")

    # Print unique Python versions across all repos
    all_versions = set()
    for versions in repo_python_versions.values():
        all_versions.update(versions)
    print(f"Total unique Python versions detected: {len(all_versions)}")
    print("All Python versions:")
    for version in sorted(all_versions):
        print(f"  - Python {version}")


if __name__ == "__main__":
    analyze_setup_commits()


# Results for princeton-nlp/SWE-bench_Lite at 1/14/2025

# Repository Setup Commit Analysis:
# ================================================================================
#
# Repository: sympy/sympy
# Number of unique setup commits: 13
# Setup commits and their Python versions:
#   - 28b41c73c12b70d6ad9f6e45109a80649c4456da: Python 3.5
#   - 3ac1464b8840d5f8b618a654f9fbf09c452fe969: Python 3.6
#   - 50b81f9f6be151014501ffac44e5dc6b2416938f: Python unknown
#   - 70381f282f2d9d039da860e391fe51649df2779d: Python 2.7
#   - 73b3f90093754c5ed1561bd885242330e3583004: Python unknown
#   - 9a6104eab0ea7ac191a09c24f3e2d79dcd66bda5: Python 3.8
#   - be161798ecc7278ccf3ffa47259e3b5fde280b7d: Python 3.8
#   - c6cb7c5602fa48034ab1bd43c2347a7e8488f12e: Python 3.8
#   - cffd4e0f86fefd4802349a9f9b19ed70934ea354: Python 3.6
#   - e53e809176de9aa0fb62e85689f8cdb669d4cacb: Python unknown
#   - ec9e3c0436fbff934fa84e22bf07f1b3ef5bfac3: Python unknown
#   - f9a6f50ec0c74d935c50a6e9c9b2cb0469570d91: Python 3.6
#   - fd40404e72921b9e52a5f9582246e4a6cd96c431: Python 3.7
# Unique Python versions detected: 5
#   - Python 2.7
#   - Python 3.5
#   - Python 3.6
#   - Python 3.7
#   - Python 3.8
#
# Repository: pytest-dev/pytest
# Number of unique setup commits: 10
# Setup commits and their Python versions:
#   - 10056865d2a4784934ce043908a0e78d0578f677: Python unknown
#   - 4ccaa987d47566e3907f2f74167c4ab7997f622f: Python unknown
#   - 634312b14a45db8d60d72016e01294284e3a18d4: Python unknown
#   - 634cde9506eb1f48dec3ec77974ee8dc952207c6: Python unknown
#   - 678c1a0745f1cf175c442c719906a1f13e496910: Python unknown
#   - 693c3b7f61d4d32f8927a74f34ce8ac56d63958e: Python unknown
#   - c2f762460f4c42547de906d53ea498dd499ea837: Python unknown
#   - d5843f89d3c008ddcb431adbc335b080a79e617e: Python unknown
#   - e2ee3144ed6e241dea8d96215fcdca18b3892551: Python unknown
#   - f36ea240fe3579f945bf5d6cc41b5e45a572249d: Python unknown
# Unique Python versions detected: 0
#
# Repository: sphinx-doc/sphinx
# Number of unique setup commits: 9
# Setup commits and their Python versions:
#   - 3b85187ffa3401e88582073c23188c147857a8a3: Python 3.5
#   - 3f560cd67239f75840cc7a439ab54d8509c855f6: Python 3.5
#   - 4f8cb861e3b29186b38248fe81e4944fd987fcce: Python 3.5
#   - 571b55328d401a6e1d50e37407df56586065a7be: Python 3.6
#   - 5afc77ee27fc01c57165ab260d3a76751f9ddb35: Python 3.5
#   - 60775ec4c4ea08509eee4b564cbf90f316021aff: Python 3.6
#   - 8939a75efaa911a12dbe6edccedf261e88bf7eef: Python 3.6
#   - 89808c6f49e1738765d18309244dca0156ee28f6: Python 3.8
#   - f92fa6443fe6f457ab0c26d41eb229e825fda5e1: Python 3.5
# Unique Python versions detected: 3
#   - Python 3.5
#   - Python 3.6
#   - Python 3.8
#
# Repository: django/django
# Number of unique setup commits: 7
# Setup commits and their Python versions:
#   - 0668164b4ac93a5be79f5b87fae83c657124d9ab: Python unknown
#   - 0fbdb9784da915fce5dcc1fe82bac9b4785749e5: Python unknown
#   - 419a78300f7cd27611196e1e464d50fd0385ff27: Python unknown
#   - 475cffd1d64c690cdad16ede4d5e81985738ceb4: Python unknown
#   - 4a72da71001f154ea60906a2f74898d32b7322a7: Python unknown
#   - 647480166bfe7532e8c471fef0146e3a17e6c0c9: Python unknown
#   - 65dfb06a1ab56c238cc80f5e1c31f61210c4577d: Python unknown
# Unique Python versions detected: 0
#
# Repository: psf/requests
# Number of unique setup commits: 5
# Setup commits and their Python versions:
#   - 091991be0da19de9108dbe5e3752917fea3d7fdc: Python unknown
#   - 36453b95b13079296776d11b09cab2567ea3e703: Python unknown
#   - 3eb69be879063de4803f7f0152b83738a1c95ca4: Python unknown
#   - a0df2cbb10419037d11d04352b3175405ab52941: Python unknown
#   - bf436ea0a49513bd4e49bb2d1645bd770e470d75: Python unknown
# Unique Python versions detected: 0
#
# Repository: astropy/astropy
# Number of unique setup commits: 4
# Setup commits and their Python versions:
#   - 298ccb478e6bf092953bca67a3d29dc6c35f6752: Python unknown
#   - 362f6df12abf9bd769d4915fabf955c993ea22cf: Python unknown
#   - 5f74eacbcc7fff707a44d8eb58adaa514cb7dcb5: Python unknown
#   - 848c8fa21332abd66b44efe3cb48b72377fb32cc: Python unknown
# Unique Python versions detected: 0
#
# Repository: matplotlib/matplotlib
# Number of unique setup commits: 4
# Setup commits and their Python versions:
#   - 0849036fd992a2dd133a0cffc3f84f58ccf1840f: Python 3.11
#   - 28289122be81e0bc0a6ee0c4c5b7343a46ce2e4e: Python 3.11
#   - 73909bcb408886a22e2b84581d6b9e6d9907c813: Python 3.11
#   - de98877e3dc45de8dd441d008f23d88738dc015d: Python 3.11
# Unique Python versions detected: 1
#   - Python 3.11
#
# Repository: scikit-learn/scikit-learn
# Number of unique setup commits: 4
# Setup commits and their Python versions:
#   - 1e8a5b833d1b58f3ab84099c4582239af854b23a: Python 3.8
#   - 55bf5d93e5674f13a1134d93a11fd0cd11aabcd1: Python unknown
#   - 7813f7efb5b2012412888b69e73d76f2df2b50b6: Python 3.5
#   - 7e85a6d1f038bbb932b36f18d75df6be937ed00d: Python 3.5
# Unique Python versions detected: 2
#   - Python 3.5
#   - Python 3.8
#
# Repository: pylint-dev/pylint
# Number of unique setup commits: 3
# Setup commits and their Python versions:
#   - 3b2fbaec045697d53bdd4435e59dbfc2b286df4b: Python unknown
#   - 680edebc686cad664bbed934a490aeafa775f163: Python unknown
#   - e90702074e68e20dc8e5df5013ee3ecf22139c3e: Python 3.7.2
# Unique Python versions detected: 1
#   - Python 3.7.2
#
# Repository: mwaskom/seaborn
# Number of unique setup commits: 2
# Setup commits and their Python versions:
#   - 23860365816440b050e9211e1c395a966de3c403: Python 3.8
#   - d25872b0fc99dbf7e666a91f59bd4ed125186aa1: Python 3.7
# Unique Python versions detected: 2
#   - Python 3.7
#   - Python 3.8
#
# Repository: pallets/flask
# Number of unique setup commits: 2
# Setup commits and their Python versions:
#   - 182ce3dd15dfa3537391c3efaf9c3ff407d134d4: Python 3.7
#   - 4346498c85848c53843b810537b83a8f6124c9d3: Python unknown
# Unique Python versions detected: 1
#   - Python 3.7
#
# Repository: pydata/xarray
# Number of unique setup commits: 1
# Setup commits and their Python versions:
#   - 1c198a191127c601d091213c4b3292a8bb3054e1: Python unknown
# Unique Python versions detected: 0
#
# Summary:
# ================================================================================
# Total repositories: 12
# Repositories with multiple setup commits: 11
# Repositories with single setup commit: 1
# Repositories with Python version detected: 12
# Total unique Python versions detected: 7
# All Python versions:
#   - Python 2.7
#   - Python 3.11
#   - Python 3.5
#   - Python 3.6
#   - Python 3.7
#   - Python 3.7.2
#   - Python 3.8
