"""Compare detected Python versions with those defined in dataset_constants."""

from pathlib import Path
import tempfile
import shutil
from git import Repo
from collections import defaultdict
from datasets import load_dataset
from typing import Dict, Optional, Set, Tuple

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
    
    print("\nComparing Python Versions:")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for repo, versions in sorted(repo_versions.items()):
            print(f"\nRepository: {repo}")
            
            # Get versions from constants
            print("Versions from constants:")
            for version in sorted(versions):
                constant_version = get_constant_python_version(repo, version)
                print(f"  {version}: Python {constant_version}")
            
            # Clone and detect versions
            repo_path = temp_path / repo.split("/")[-1]
            detected_versions: Dict[str, str] = {}
            
            try:
                print("\nDetected versions from commits:")
                repo_obj = Repo.clone_from(f"https://github.com/{repo}", str(repo_path))
                
                for commit, version in repo_commits[repo].items():
                    try:
                        repo_obj.git.checkout(commit)
                        detected = detect_python_version(repo_path)
                        detected_versions[commit] = detected
                        constant = get_constant_python_version(repo, version)
                        
                        match = "✓" if detected == constant else "✗"
                        print(f"  {commit} ({version})")
                        print(f"    Detected: Python {detected}")
                        print(f"    Constant: Python {constant}  {match}")
                        
                    except Exception as e:
                        print(f"  Error checking {commit}: {e}")
                
            except Exception as e:
                print(f"Error analyzing repo {repo}: {e}")
            finally:
                if repo_path.exists():
                    shutil.rmtree(repo_path)
            
            print("\nSummary for this repo:")
            matches = sum(1 for commit, version in repo_commits[repo].items()
                         if detected_versions.get(commit) == 
                         get_constant_python_version(repo, version))
            total = len(repo_commits[repo])
            print(f"Matching versions: {matches}/{total}")


if __name__ == "__main__":
    analyze_version_differences()
