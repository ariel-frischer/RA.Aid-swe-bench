# SWE Lite RA-AID

A lightweight version of SWE Bench focused on the RA-AID agent.

## Description

Streamlined interface for running the RA-AID agent on the SWE Bench dataset. It's designed to make it easier to test and evaluate the RA-AID agent's performance on software engineering tasks.
Many of the files in this repo have been modified from the source: https://github.com/Aider-AI/aider-swe-bench
[Read more about swebench here.](https://www.swebench.com/)

## Requirements

- Python >=3.9, <3.13
- Poetry for this project's dependency management
- RA-AID ^0.12.0 (must have `ra-aid` cli path working in the running shell)
- uv for fast dependency installation for each attempt

## Installation

```bash
# Clone the repository
git clone https://github.com/ariel-frischer/RA.Aid-swe-bench
cd swe-lite-ra-aid

# Install dependencies using Poetry
poetry install
```

## Usage

The main workflow consists of:

1. Generate predictions using the RA-AID model:
```bash
make run
```
This will process the SWE-bench Lite dataset and generate predictions in the `predictions/ra_aid_predictions` directory.
You may want to modify `MAX_THREADS` which determines how many agents run in parallel located in `swe_lite_ra_aid/main.py`.

NOTE: Shell env variables like AIDER_MODEL="openrouter/deepseek/deepseek-chat" will effect the coder model used by aider while running!

2. (WIP) Evaluate predictions and generate a report:

IN DEVELOPMENT

```bash
make evaluate
```
This will run the evaluation pipeline and generate a detailed report of model performance.


### Available Make Commands

```bash
make install          # Install project dependencies using Poetry
make run             # Run the main prediction script
make test            # Run tests using pytest
make clean           # Remove Python cache files and predictions
make format          # Format code using black
make clean-repos     # Clean up cloned repositories
make clean-predictions # Remove all prediction files (with confirmation)
make add-model-name  # Add model metadata to predictions
make evaluate        # Run evaluation and generate report
make check          # Run ruff linter with auto-fix
make aider          # Run aider in the current directory
```

### Repository Management

The project uses a `RepoManager` class to efficiently handle repository operations:

1. **Repository Caching**:
   - Base repositories are cached in the `repos/` directory
   - Each repository is cloned once and reused across multiple attempts
   - Dependencies are installed in a virtual environment within the cached repo
   - Format: `repos/owner__repo/` (e.g., `repos/django__django/`)

2. **Worktree System**:
   - For each attempt, a new git worktree is created from the cached repo
   - Worktrees share the same .venv through symlinks to save space and setup time
   - Each worktree gets a unique name: `worktree-{commit}-{random}`
   - Worktrees are automatically cleaned up after each attempt

3. **Dependency Management**:
   - Uses `uv` for fast Python package installation
   - Virtual environments are created once per cached repo
   - Handles various dependency files:
     - pyproject.toml
     - requirements.txt
     - requirements-dev.txt
     - setup.py

This system significantly reduces disk usage and speeds up multiple attempts by:
- Avoiding repeated cloning of repositories
- Reusing installed dependencies
- Sharing virtual environments across attempts

## Winner File Selection

For each task, the system makes up to 3 attempts to solve the problem. Each prediction file includes an `is_winner` boolean field that indicates whether it's currently considered the best solution. The winner is selected based on these criteria:

1. The attempt that modifies the most files wins (higher `num_edited_files`)
2. If multiple attempts modify the same number of files, the one with the longer patch wins (longer `model_patch`)
3. Earlier attempts are replaced as winners if later attempts score better on these criteria

The `is_winner` field is automatically updated in all related prediction files when a new winner is selected. When evaluating results, you can filter for files with `is_winner=true` to get the best prediction for each task.

Note: As mentioned in Problems/Improvements below, this selection criteria may not be optimal - using the number of passing tests would be a better metric.

## Problems/Improvements
* RA.Aid does get stuck often, multiple different errors.
  * Tool Error: Error executing code: invalid syntax (, line 4)
  * Tool Error: Error executing code: unterminated string literal (detected at line 1) (, line 1) 
  * Tool Error: Error executing code: /tmp/tmplwzqokro/sympy/sympy
  * Tool Error: Error executing code: unmatched ')' (, line 1)                                                │
* Logging setup needed.
* We don't automate `test_cmd` or run more attempts based on it. If we automate
  this, we will have an indicator to run more attempts and get improved winner
  attempt selection.
* Winner attempt should be selected based on a hierchy. The attempt with the most passing tests should win.
* Aider repomap will regenerate a repomap for each attempt, not optimal.
* Would be nice to be ablee to extract and pass `test_cmd` and `lint_cmd` to aider when make code changes.
* Need to modify `pick_winner` method for RA.Aid, the original `choose_predictions` method doesnt work well with RA-Aid.
* Running locally with cowboy mode seems dangerous if RA.Aid can run ANY command?!
* Shell env variables like AIDER_MODEL="openrouter/deepseek/deepseek-chat" will effect the coder model used by aider while running!
* We are not calculating costs for each attempt. Need a way to extract accurate costs in predictions json then compile them in evaluation.
* This can get pricey $$$ quickly be careful which model you choose. I'm using deepseek/deepseek-chat for now.
* Not ideal to use poetry for this projects dependencies, then use uv for problem repo dependencies. Prefer `uv` as it seems much faster.

## Dataset Structure

### SWE-bench_Lite
https://huggingface.co/datasets/princeton-nlp/
```
An example of a SWE-bench datum is as follows:
instance_id: (str) - A formatted instance identifier, usually as repo_owner__repo_name-PR-number.
patch: (str) - The gold patch, the patch generated by the PR (minus test-related code), that resolved the issue.
repo: (str) - The repository owner/name identifier from GitHub.
base_commit: (str) - The commit hash of the repository representing the HEAD of the repository before the solution PR is applied.
hints_text: (str) - Comments made on the issue prior to the creation of the solution PR’s first commit creation date.
created_at: (str) - The creation date of the pull request.
test_patch: (str) - A test-file patch that was contributed by the solution PR.
problem_statement: (str) - The issue title and body.
version: (str) - Installation version to use for running evaluation.
environment_setup_commit: (str) - commit hash to use for environment setup and installation.
FAIL_TO_PASS: (str) - A json list of strings that represent the set of tests resolved by the PR and tied to the issue resolution.
PASS_TO_PASS: (str) - A json list of strings that represent tests that should pass before and after the PR application.
```

## License

Apache 2.0 License
