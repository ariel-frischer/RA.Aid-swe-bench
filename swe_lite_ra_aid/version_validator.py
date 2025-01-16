"""Compare detected Python versions with those defined in dataset_constants."""

from pathlib import Path
import tempfile
import shutil
from git import Repo
from collections import defaultdict
from datasets import load_dataset
from typing import Dict, Optional, Set

from .dataset_constants import MAP_VERSION_TO_INSTALL
from .uv_utils import detect_python_version


def get_constant_python_version(repo: str, version: str) -> Optional[str]:
    """Get Python version from MAP_VERSION_TO_INSTALL constants."""
    if repo not in MAP_VERSION_TO_INSTALL:
        return None
    
    version_map = MAP_VERSION_TO_INSTALL[repo]
    if version not in version_map:
        return None
        
    return version_map[version].get("python")


def analyze_version_differences():
    """Compare detected Python versions with those defined in constants."""
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    # Collect repo versions and commits
    repo_versions: Dict[str, Set[str]] = defaultdict(set)
    repo_commits: Dict[str, Dict[str, str]] = defaultdict(dict)  # repo -> {commit -> version}
    
    for instance in dataset:
        repo = instance["repo"]
        version = instance["version"]
        commit = instance["environment_setup_commit"]
        repo_versions[repo].add(version)
        repo_commits[repo][commit] = version
    
    logger.info("\nComparing Python Versions:")
    logger.info("=" * 80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for repo, versions in sorted(repo_versions.items()):
            logger.info(f"\nRepository: {repo}")
            
            # Clone and detect versions
            repo_path = temp_path / repo.split("/")[-1]
            detected_versions: Dict[str, str] = {}
            matches = 0
            total = 0
    
            try:
                logger.info("\nAnalyzing commits:")
                repo_obj = Repo.clone_from(f"https://github.com/{repo}", str(repo_path))
        
                for commit, version in repo_commits[repo].items():
                    total += 1
                    try:
                        # Get version from constants for this repo+version
                        constant = get_constant_python_version(repo, version)
                
                        # Detect version from commit
                        repo_obj.git.checkout(commit)
                        detected = detect_python_version(repo_path)
                        detected_versions[commit] = detected
                
                        match = "✓" if detected == constant else "✗"
                        if detected == constant:
                            matches += 1
                    
                        logger.info(f"\n  Commit: {commit}")
                        logger.info(f"  Repository version: {version}")
                        logger.info(f"  Constants Python: {constant}")
                        logger.info(f"  Detected Python: {detected}  {match}")
                        
                    except Exception as e:
                        logger.error(f"  Error checking {commit}: {e}")
                
            except Exception as e:
                logger.error(f"Error analyzing repo {repo}: {e}")
            finally:
                if repo_path.exists():
                    shutil.rmtree(repo_path)
            
            logger.info("\nSummary for this repo:")
            logger.info(f"Matching versions: {matches}/{total}")
            if total > 0:
                logger.info(f"Match rate: {(matches/total)*100:.1f}%")


if __name__ == "__main__":
    analyze_version_differences()

# Results on 1/14/2025 show that detect_python_version() seems to detect all of them incorrectly :/
# Deleted detect_python_version() in favor of hard-coded constants.py retrieval.

# Comparing Python Versions:
# ================================================================================
#
# Repository: astropy/astropy
#
# Analyzing commits:
# Error analyzing repo astropy/astropy: Cmd('git') failed due to: exit code(128)
#   cmdline: git clone -v -- https://github.com/astropy/astropy /tmp/tmp9rikhior/astropy
#   stderr: 'Cloning into '/tmp/tmp9rikhior/astropy'...
# POST git-upload-pack (175 bytes)
# POST git-upload-pack (gzip 9767 to 4919 bytes)
# error: RPC failed; curl 92 HTTP/2 stream 5 was not closed cleanly: CANCEL (err 8)
# error: 7148 bytes of body are still expected
# fetch-pack: unexpected disconnect while reading sideband packet
# fatal: early EOF
# fatal: fetch-pack: invalid index-pack output
# '
#
# Summary for this repo:
# Matching versions: 0/0
#
# Repository: django/django
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/django
# Checking setup.py at: /tmp/tmp9rikhior/django/setup.py
#   Found version constraint: None from >={}.{}
# Checking tox.ini at: /tmp/tmp9rikhior/django/tox.ini
# No Python version found for django
#
#   Commit: 419a78300f7cd27611196e1e464d50fd0385ff27
#   Repository version: 3.0
#   Constants Python: 3.6
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/django
# Checking setup.py at: /tmp/tmp9rikhior/django/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/django/tox.ini
# No Python version found for django
#
#   Commit: 0668164b4ac93a5be79f5b87fae83c657124d9ab
#   Repository version: 3.1
#   Constants Python: 3.6
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/django
# Checking setup.py at: /tmp/tmp9rikhior/django/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/django/tox.ini
# No Python version found for django
#
#   Commit: 65dfb06a1ab56c238cc80f5e1c31f61210c4577d
#   Repository version: 3.2
#   Constants Python: 3.6
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/django
# Checking pyproject.toml at: /tmp/tmp9rikhior/django/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/django/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/django/tox.ini
# No Python version found for django
#
#   Commit: 475cffd1d64c690cdad16ede4d5e81985738ceb4
#   Repository version: 4.0
#   Constants Python: 3.8
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/django
# Checking pyproject.toml at: /tmp/tmp9rikhior/django/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/django/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/django/tox.ini
# No Python version found for django
#
#   Commit: 647480166bfe7532e8c471fef0146e3a17e6c0c9
#   Repository version: 4.1
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/django
# Checking pyproject.toml at: /tmp/tmp9rikhior/django/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/django/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/django/tox.ini
# No Python version found for django
#
#   Commit: 0fbdb9784da915fce5dcc1fe82bac9b4785749e5
#   Repository version: 4.2
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/django
# Checking pyproject.toml at: /tmp/tmp9rikhior/django/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/django/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/django/tox.ini
# No Python version found for django
#
#   Commit: 4a72da71001f154ea60906a2f74898d32b7322a7
#   Repository version: 5.0
#   Constants Python: 3.11
#   Detected Python: None  ✗
#
# Summary for this repo:
# Matching versions: 0/7
# Match rate: 0.0%
#
# Repository: matplotlib/matplotlib
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/matplotlib
# Checking pyproject.toml at: /tmp/tmp9rikhior/matplotlib/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/matplotlib/setup.py
#   Found version constraint: None from >={}
# Checking tox.ini at: /tmp/tmp9rikhior/matplotlib/tox.ini
# Using default fallback version 3.11 for matplotlib
#
#   Commit: 28289122be81e0bc0a6ee0c4c5b7343a46ce2e4e
#   Repository version: 3.3
#   Constants Python: 3.8
#   Detected Python: 3.11  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/matplotlib
# Checking setup.py at: /tmp/tmp9rikhior/matplotlib/setup.py
#   Found version constraint: None from >={}
# Checking tox.ini at: /tmp/tmp9rikhior/matplotlib/tox.ini
# Using default fallback version 3.11 for matplotlib
#
#   Commit: de98877e3dc45de8dd441d008f23d88738dc015d
#   Repository version: 3.5
#   Constants Python: 3.9
#   Detected Python: 3.11  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/matplotlib
# Checking pyproject.toml at: /tmp/tmp9rikhior/matplotlib/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/matplotlib/setup.py
#   Found version constraint: None from >={}
# Checking tox.ini at: /tmp/tmp9rikhior/matplotlib/tox.ini
# Using default fallback version 3.11 for matplotlib
#
#   Commit: 73909bcb408886a22e2b84581d6b9e6d9907c813
#   Repository version: 3.6
#   Constants Python: 3.9
#   Detected Python: 3.11  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/matplotlib
# Checking pyproject.toml at: /tmp/tmp9rikhior/matplotlib/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/matplotlib/setup.py
#   Found version constraint: None from >={}
# Checking tox.ini at: /tmp/tmp9rikhior/matplotlib/tox.ini
# Using default fallback version 3.11 for matplotlib
#
#   Commit: 0849036fd992a2dd133a0cffc3f84f58ccf1840f
#   Repository version: 3.7
#   Constants Python: 3.9
#   Detected Python: 3.11  ✗
#
# Summary for this repo:
# Matching versions: 0/4
# Match rate: 0.0%
#
# Repository: mwaskom/seaborn
#
# Analyzing commits:
# Error analyzing repo mwaskom/seaborn: Cmd('git') failed due to: exit code(128)
#   cmdline: git clone -v -- https://github.com/mwaskom/seaborn /tmp/tmp9rikhior/seaborn
#   stderr: 'Cloning into '/tmp/tmp9rikhior/seaborn'...
# POST git-upload-pack (175 bytes)
# POST git-upload-pack (gzip 3217 to 1611 bytes)
# error: RPC failed; curl 92 HTTP/2 stream 5 was not closed cleanly: CANCEL (err 8)
# error: 4747 bytes of body are still expected
# fetch-pack: unexpected disconnect while reading sideband packet
# fatal: early EOF
# fatal: fetch-pack: invalid index-pack output
# '
#
# Summary for this repo:
# Matching versions: 0/0
#
# Repository: pallets/flask
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/flask
# Checking setup.py at: /tmp/tmp9rikhior/flask/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/flask/tox.ini
# No Python version found for flask
#
#   Commit: 4346498c85848c53843b810537b83a8f6124c9d3
#   Repository version: 2.0
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/flask
# Checking pyproject.toml at: /tmp/tmp9rikhior/flask/pyproject.toml
#   Found version constraint: 3.7 from >=3.7
# Found version 3.7 in pyproject.toml
#
#   Commit: 182ce3dd15dfa3537391c3efaf9c3ff407d134d4
#   Repository version: 2.3
#   Constants Python: 3.11
#   Detected Python: 3.7  ✗
#
# Summary for this repo:
# Matching versions: 0/2
# Match rate: 0.0%
#
# Repository: psf/requests
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/requests
# Checking setup.py at: /tmp/tmp9rikhior/requests/setup.py
# Checking requirements.txt at: /tmp/tmp9rikhior/requests/requirements.txt
# No Python version found for requests
#
#   Commit: 3eb69be879063de4803f7f0152b83738a1c95ca4
#   Repository version: 2.3
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/requests
# Checking setup.py at: /tmp/tmp9rikhior/requests/setup.py
# Checking requirements.txt at: /tmp/tmp9rikhior/requests/requirements.txt
# No Python version found for requests
#
#   Commit: 091991be0da19de9108dbe5e3752917fea3d7fdc
#   Repository version: 2.4
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/requests
# Checking setup.py at: /tmp/tmp9rikhior/requests/setup.py
# Checking requirements.txt at: /tmp/tmp9rikhior/requests/requirements.txt
# No Python version found for requests
#
#   Commit: bf436ea0a49513bd4e49bb2d1645bd770e470d75
#   Repository version: 2.7
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/requests
# Checking setup.py at: /tmp/tmp9rikhior/requests/setup.py
# Checking requirements.txt at: /tmp/tmp9rikhior/requests/requirements.txt
# No Python version found for requests
#
#   Commit: 36453b95b13079296776d11b09cab2567ea3e703
#   Repository version: 2.10
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/requests
# Checking setup.py at: /tmp/tmp9rikhior/requests/setup.py
# Checking requirements.txt at: /tmp/tmp9rikhior/requests/requirements.txt
# No Python version found for requests
#
#   Commit: a0df2cbb10419037d11d04352b3175405ab52941
#   Repository version: 0.14
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Summary for this repo:
# Matching versions: 0/5
# Match rate: 0.0%
#
# Repository: pydata/xarray
#
# Analyzing commits:
# Error analyzing repo pydata/xarray: Cmd('git') failed due to: exit code(128)
#   cmdline: git clone -v -- https://github.com/pydata/xarray /tmp/tmp9rikhior/xarray
#   stderr: 'Cloning into '/tmp/tmp9rikhior/xarray'...
# POST git-upload-pack (175 bytes)
# POST git-upload-pack (gzip 5367 to 2713 bytes)
# error: RPC failed; curl 92 HTTP/2 stream 5 was not closed cleanly: CANCEL (err 8)
# error: 3031 bytes of body are still expected
# fetch-pack: unexpected disconnect while reading sideband packet
# fatal: early EOF
# fatal: fetch-pack: invalid index-pack output
# '
#
# Summary for this repo:
# Matching versions: 0/0
#
# Repository: pylint-dev/pylint
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/pylint
# Checking setup.py at: /tmp/tmp9rikhior/pylint/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/pylint/tox.ini
# No Python version found for pylint
#
#   Commit: 3b2fbaec045697d53bdd4435e59dbfc2b286df4b
#   Repository version: 2.13
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/pylint
# Checking setup.py at: /tmp/tmp9rikhior/pylint/setup.py
# Checking tox.ini at: /tmp/tmp9rikhior/pylint/tox.ini
# No Python version found for pylint
#
#   Commit: 680edebc686cad664bbed934a490aeafa775f163
#   Repository version: 2.14
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/pylint
# Checking pyproject.toml at: /tmp/tmp9rikhior/pylint/pyproject.toml
#   Found version constraint: 3.7.2 from >=3.7.2
# Found version 3.7.2 in pyproject.toml
#
#   Commit: e90702074e68e20dc8e5df5013ee3ecf22139c3e
#   Repository version: 2.15
#   Constants Python: 3.9
#   Detected Python: 3.7.2  ✗
#
# Summary for this repo:
# Matching versions: 0/3
# Match rate: 0.0%
#
# Repository: pytest-dev/pytest
#
# Analyzing commits:
# Error analyzing repo pytest-dev/pytest: Cmd('git') failed due to: exit code(128)
#   cmdline: git clone -v -- https://github.com/pytest-dev/pytest /tmp/tmp9rikhior/pytest
#   stderr: 'Cloning into '/tmp/tmp9rikhior/pytest'...
# POST git-upload-pack (175 bytes)
# POST git-upload-pack (gzip 12267 to 6159 bytes)
# error: RPC failed; curl 92 HTTP/2 stream 5 was not closed cleanly: CANCEL (err 8)
# error: 16 bytes of body are still expected
# fetch-pack: unexpected disconnect while reading sideband packet
# fatal: early EOF
# fatal: fetch-pack: invalid index-pack output
# '
#
# Summary for this repo:
# Matching versions: 0/0
#
# Repository: scikit-learn/scikit-learn
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/scikit-learn
# Checking setup.py at: /tmp/tmp9rikhior/scikit-learn/setup.py
# No Python version found for scikit-learn
#
#   Commit: 55bf5d93e5674f13a1134d93a11fd0cd11aabcd1
#   Repository version: 0.20
#   Constants Python: 3.6
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/scikit-learn
# Checking setup.py at: /tmp/tmp9rikhior/scikit-learn/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: 7813f7efb5b2012412888b69e73d76f2df2b50b6
#   Repository version: 0.21
#   Constants Python: 3.6
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/scikit-learn
# Checking setup.py at: /tmp/tmp9rikhior/scikit-learn/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: 7e85a6d1f038bbb932b36f18d75df6be937ed00d
#   Repository version: 0.22
#   Constants Python: 3.6
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/scikit-learn
# Checking pyproject.toml at: /tmp/tmp9rikhior/scikit-learn/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/scikit-learn/setup.py
#   Found version constraint: 3.8 from >=3.8
# Found version 3.8 in setup.py
#
#   Commit: 1e8a5b833d1b58f3ab84099c4582239af854b23a
#   Repository version: 1.3
#   Constants Python: 3.9
#   Detected Python: 3.8  ✗
#
# Summary for this repo:
# Matching versions: 0/4
# Match rate: 0.0%
#
# Repository: sphinx-doc/sphinx
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.6 from >=3.6
# Found version 3.6 in setup.py
#
#   Commit: 60775ec4c4ea08509eee4b564cbf90f316021aff
#   Repository version: 5.0
#   Constants Python: 3.9
#   Detected Python: 3.6  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.6 from >=3.6
# Found version 3.6 in setup.py
#
#   Commit: 571b55328d401a6e1d50e37407df56586065a7be
#   Repository version: 5.1
#   Constants Python: 3.9
#   Detected Python: 3.6  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking pyproject.toml at: /tmp/tmp9rikhior/sphinx/pyproject.toml
#   Found version constraint: 3.8 from >=3.8
# Found version 3.8 in pyproject.toml
#
#   Commit: 89808c6f49e1738765d18309244dca0156ee28f6
#   Repository version: 7.1
#   Constants Python: 3.9
#   Detected Python: 3.8  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: 5afc77ee27fc01c57165ab260d3a76751f9ddb35
#   Repository version: 3.1
#   Constants Python: 3.9
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: f92fa6443fe6f457ab0c26d41eb229e825fda5e1
#   Repository version: 3.2
#   Constants Python: 3.9
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: 3b85187ffa3401e88582073c23188c147857a8a3
#   Repository version: 3.3
#   Constants Python: 3.9
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: 3f560cd67239f75840cc7a439ab54d8509c855f6
#   Repository version: 3.4
#   Constants Python: 3.9
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: 4f8cb861e3b29186b38248fe81e4944fd987fcce
#   Repository version: 3.5
#   Constants Python: 3.9
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sphinx
# Checking setup.py at: /tmp/tmp9rikhior/sphinx/setup.py
#   Found version constraint: 3.6 from >=3.6
# Found version 3.6 in setup.py
#
#   Commit: 8939a75efaa911a12dbe6edccedf261e88bf7eef
#   Repository version: 4.0
#   Constants Python: 3.9
#   Detected Python: 3.6  ✗
#
# Summary for this repo:
# Matching versions: 0/9
# Match rate: 0.0%
#
# Repository: sympy/sympy
#
# Analyzing commits:
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
# No Python version found for sympy
#
#   Commit: 50b81f9f6be151014501ffac44e5dc6b2416938f
#   Repository version: 1.0
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
# No Python version found for sympy
#
#   Commit: ec9e3c0436fbff934fa84e22bf07f1b3ef5bfac3
#   Repository version: 1.1
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
# No Python version found for sympy
#
#   Commit: e53e809176de9aa0fb62e85689f8cdb669d4cacb
#   Repository version: 1.2
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
# No Python version found for sympy
#
#   Commit: 73b3f90093754c5ed1561bd885242330e3583004
#   Repository version: 1.4
#   Constants Python: 3.9
#   Detected Python: None  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 2.7 from >=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*
# Found version 2.7 in setup.py
#
#   Commit: 70381f282f2d9d039da860e391fe51649df2779d
#   Repository version: 1.5
#   Constants Python: 3.9
#   Detected Python: 2.7  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.5 from >=3.5
# Found version 3.5 in setup.py
#
#   Commit: 28b41c73c12b70d6ad9f6e45109a80649c4456da
#   Repository version: 1.6
#   Constants Python: 3.9
#   Detected Python: 3.5  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.6 from >=3.6
# Found version 3.6 in setup.py
#
#   Commit: cffd4e0f86fefd4802349a9f9b19ed70934ea354
#   Repository version: 1.7
#   Constants Python: 3.9
#   Detected Python: 3.6  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.6 from >=3.6
# Found version 3.6 in setup.py
#
#   Commit: 3ac1464b8840d5f8b618a654f9fbf09c452fe969
#   Repository version: 1.8
#   Constants Python: 3.9
#   Detected Python: 3.6  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.6 from >=3.6
# Found version 3.6 in setup.py
#
#   Commit: f9a6f50ec0c74d935c50a6e9c9b2cb0469570d91
#   Repository version: 1.9
#   Constants Python: 3.9
#   Detected Python: 3.6  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.7 from >=3.7
# Found version 3.7 in setup.py
#
#   Commit: fd40404e72921b9e52a5f9582246e4a6cd96c431
#   Repository version: 1.10
#   Constants Python: 3.9
#   Detected Python: 3.7  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.8 from >=3.8
# Found version 3.8 in setup.py
#
#   Commit: 9a6104eab0ea7ac191a09c24f3e2d79dcd66bda5
#   Repository version: 1.11
#   Constants Python: 3.9
#   Detected Python: 3.8  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.8 from >=3.8
# Found version 3.8 in setup.py
#
#   Commit: c6cb7c5602fa48034ab1bd43c2347a7e8488f12e
#   Repository version: 1.12
#   Constants Python: 3.9
#   Detected Python: 3.8  ✗
#
# Detecting Python version for repo at: /tmp/tmp9rikhior/sympy
# Checking pyproject.toml at: /tmp/tmp9rikhior/sympy/pyproject.toml
# Checking setup.py at: /tmp/tmp9rikhior/sympy/setup.py
#   Found version constraint: 3.8 from >=3.8
# Found version 3.8 in setup.py
#
#   Commit: be161798ecc7278ccf3ffa47259e3b5fde280b7d
#   Repository version: 1.13
#   Constants Python: 3.9
#   Detected Python: 3.8  ✗
#
# Summary for this repo:
# Matching versions: 0/13
# Match rate: 0.0%
