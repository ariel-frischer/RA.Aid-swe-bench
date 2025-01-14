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


# Results for princeton-nlp/SWE-bench_Lite at 1/14/2025

# Repository Setup Commit Analysis:
# ================================================================================
#
# Repository: sympy/sympy
# Number of unique setup commits: 13
# Setup commits:
#   - 28b41c73c12b70d6ad9f6e45109a80649c4456da
#   - 3ac1464b8840d5f8b618a654f9fbf09c452fe969
#   - 50b81f9f6be151014501ffac44e5dc6b2416938f
#   - 70381f282f2d9d039da860e391fe51649df2779d
#   - 73b3f90093754c5ed1561bd885242330e3583004
#   - 9a6104eab0ea7ac191a09c24f3e2d79dcd66bda5
#   - be161798ecc7278ccf3ffa47259e3b5fde280b7d
#   - c6cb7c5602fa48034ab1bd43c2347a7e8488f12e
#   - cffd4e0f86fefd4802349a9f9b19ed70934ea354
#   - e53e809176de9aa0fb62e85689f8cdb669d4cacb
#   - ec9e3c0436fbff934fa84e22bf07f1b3ef5bfac3
#   - f9a6f50ec0c74d935c50a6e9c9b2cb0469570d91
#   - fd40404e72921b9e52a5f9582246e4a6cd96c431
#
# Repository: pytest-dev/pytest
# Number of unique setup commits: 10
# Setup commits:
#   - 10056865d2a4784934ce043908a0e78d0578f677
#   - 4ccaa987d47566e3907f2f74167c4ab7997f622f
#   - 634312b14a45db8d60d72016e01294284e3a18d4
#   - 634cde9506eb1f48dec3ec77974ee8dc952207c6
#   - 678c1a0745f1cf175c442c719906a1f13e496910
#   - 693c3b7f61d4d32f8927a74f34ce8ac56d63958e
#   - c2f762460f4c42547de906d53ea498dd499ea837
#   - d5843f89d3c008ddcb431adbc335b080a79e617e
#   - e2ee3144ed6e241dea8d96215fcdca18b3892551
#   - f36ea240fe3579f945bf5d6cc41b5e45a572249d
#
# Repository: sphinx-doc/sphinx
# Number of unique setup commits: 9
# Setup commits:
#   - 3b85187ffa3401e88582073c23188c147857a8a3
#   - 3f560cd67239f75840cc7a439ab54d8509c855f6
#   - 4f8cb861e3b29186b38248fe81e4944fd987fcce
#   - 571b55328d401a6e1d50e37407df56586065a7be
#   - 5afc77ee27fc01c57165ab260d3a76751f9ddb35
#   - 60775ec4c4ea08509eee4b564cbf90f316021aff
#   - 8939a75efaa911a12dbe6edccedf261e88bf7eef
#   - 89808c6f49e1738765d18309244dca0156ee28f6
#   - f92fa6443fe6f457ab0c26d41eb229e825fda5e1
#
# Repository: django/django
# Number of unique setup commits: 7
# Setup commits:
#   - 0668164b4ac93a5be79f5b87fae83c657124d9ab
#   - 0fbdb9784da915fce5dcc1fe82bac9b4785749e5
#   - 419a78300f7cd27611196e1e464d50fd0385ff27
#   - 475cffd1d64c690cdad16ede4d5e81985738ceb4
#   - 4a72da71001f154ea60906a2f74898d32b7322a7
#   - 647480166bfe7532e8c471fef0146e3a17e6c0c9
#   - 65dfb06a1ab56c238cc80f5e1c31f61210c4577d
#
# Repository: psf/requests
# Number of unique setup commits: 5
# Setup commits:
#   - 091991be0da19de9108dbe5e3752917fea3d7fdc
#   - 36453b95b13079296776d11b09cab2567ea3e703
#   - 3eb69be879063de4803f7f0152b83738a1c95ca4
#   - a0df2cbb10419037d11d04352b3175405ab52941
#   - bf436ea0a49513bd4e49bb2d1645bd770e470d75
#
# Repository: astropy/astropy
# Number of unique setup commits: 4
# Setup commits:
#   - 298ccb478e6bf092953bca67a3d29dc6c35f6752
#   - 362f6df12abf9bd769d4915fabf955c993ea22cf
#   - 5f74eacbcc7fff707a44d8eb58adaa514cb7dcb5
#   - 848c8fa21332abd66b44efe3cb48b72377fb32cc
#
# Repository: matplotlib/matplotlib
# Number of unique setup commits: 4
# Setup commits:
#   - 0849036fd992a2dd133a0cffc3f84f58ccf1840f
#   - 28289122be81e0bc0a6ee0c4c5b7343a46ce2e4e
#   - 73909bcb408886a22e2b84581d6b9e6d9907c813
#   - de98877e3dc45de8dd441d008f23d88738dc015d
#
# Repository: scikit-learn/scikit-learn
# Number of unique setup commits: 4
# Setup commits:
#   - 1e8a5b833d1b58f3ab84099c4582239af854b23a
#   - 55bf5d93e5674f13a1134d93a11fd0cd11aabcd1
#   - 7813f7efb5b2012412888b69e73d76f2df2b50b6
#   - 7e85a6d1f038bbb932b36f18d75df6be937ed00d
#
# Repository: pylint-dev/pylint
# Number of unique setup commits: 3
# Setup commits:
#   - 3b2fbaec045697d53bdd4435e59dbfc2b286df4b
#   - 680edebc686cad664bbed934a490aeafa775f163
#   - e90702074e68e20dc8e5df5013ee3ecf22139c3e
#
# Repository: mwaskom/seaborn
# Number of unique setup commits: 2
# Setup commits:
#   - 23860365816440b050e9211e1c395a966de3c403
#   - d25872b0fc99dbf7e666a91f59bd4ed125186aa1
#
# Repository: pallets/flask
# Number of unique setup commits: 2
# Setup commits:
#   - 182ce3dd15dfa3537391c3efaf9c3ff407d134d4
#   - 4346498c85848c53843b810537b83a8f6124c9d3
#
# Repository: pydata/xarray
# Number of unique setup commits: 1
# Setup commits:
#   - 1c198a191127c601d091213c4b3292a8bb3054e1
#
# Summary:
# ================================================================================
# Total repositories: 12
# Repositories with multiple setup commits: 11
# Repositories with single setup commit: 1
