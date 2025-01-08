# SWE Lite RA-AID

A lightweight version of SWE Bench focused on the RA-AID agent.

## Description

This project provides a streamlined interface for running the RA-AID agent on the SWE Bench dataset. It's designed to make it easier to test and evaluate the RA-AID agent's performance on software engineering tasks.
Many of the files in this repo have been modified from the source: https://github.com/Aider-AI/aider-swe-bench

## Installation

```bash
# Clone the repository
git clone https://gitlab.com/ariel-frischer/swe-lite-ra-aid.git
cd swe-lite-ra-aid

# Install dependencies using Poetry
poetry install
```

## Requirements

- Python >=3.9, <3.13
- Poetry for dependency management
- RA-AID ^0.12.0

## Usage

The main workflow consists of:

1. Generate predictions using the RA-AID model:
```bash
make run
```
This will process the SWE-bench Lite dataset and generate predictions in the `predictions/ra_aid_predictions` directory.
You may want to modify `MAX_THREADS` which determines how many agents run in parallel located in `swe_lite_ra_aid/main.py`.

2. (WIP) Evaluate predictions and generate a report:

IN DEVELOPMPENT

```bash
make evaluate
```
This will run the evaluation pipeline and generate a detailed report of model performance.


### Available Make Commands

```bash
make install      # Install project dependencies using Poetry
make run         # Run the main prediction script
make test        # Run tests using pytest
make clean       # Remove Python cache files and predictions
make format      # Format code using black
make clean-repos # Clean up cloned repositories
make add-model-name # Add model metadata to predictions
make evaluate    # Run evaluation and generate report
```

## Problems/Improvements
* RA.Aid does get stuck often, multiple different errors.
  * Tool Error: Error executing code: invalid syntax (, line 4)
  * Tool Error: Error executing code: unterminated string literal (detected at line 1) (, line 1) 
  * Tool Error: Error executing code: /tmp/tmplwzqokro/sympy/sympy
  * Tool Error: Error executing code: unmatched ')' (, line 1)                                                │
* RA.Aid seems to not make any code changes often but complete all its tasks.
  For example the research agent does one research task and is done? Prompt engineering or
  model changes can hopefully improve this.
* Need a cheaper model unless your willing to break the bank. I'm using deepseek/deepseek-chat for now.
* Aider repomap will regenerate a repomap for each attempt, does not seem optimal.
* Need to extract and pass the correct `test_cmd` and `lint_cmd` to aider when make code changes.
* Need to modify `pick_winner` method for RA.Aid, `choose_predictions` doesnt work well without it.
* Running locally with cowboy mode seems dangerous if RA.Aid can run ANY command?!

## Dataset Structure
Data Instances

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


## License

MIT License
