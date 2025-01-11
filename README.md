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

### Environment Variables

Depending on your chosen model in `config.py`, you'll need to set appropriate API keys:
- OpenAI models: `OPENAI_API_KEY`
- Anthropic models: `ANTHROPIC_API_KEY`
- OpenRouter models: `OPENROUTER_API_KEY`

These can be set in your shell or in a `.env` file in the project root.

### ⚠️ Important Notes

- **Parallel Processing**: The `MAX_THREADS` setting in `config.py` determines how many model instances run in parallel. Be cautious with high values as this can:
  - Significantly increase API costs
  - Potentially trigger rate limits
  - Cause memory/CPU issues
  
- **Cost Warning**: Different models have varying pricing. Running multiple instances in parallel with expensive models can quickly accumulate significant costs. Monitor your usage carefully!

## Installation

```bash
git clone https://github.com/ariel-frischer/RA.Aid-swe-bench
cd swe-lite-ra-aid

poetry install
```

## Usage

The main workflow consists of:

1. Generate predictions using the RA-AID model:
```bash
make run
```
This will process the SWE-bench Lite dataset and generate predictions in the `predictions/ra_aid_predictions` directory.
You may want to modify `MAX_THREADS` which determines how many agents run in parallel located in `swe_lite_ra_aid/config.py`.
The `RepoManager` handles cloning, dependency installation, and caching for each problem repo.

2. Evaluate predictions and generate a report:

The evaluation pipeline processes predictions and generates detailed reports on model performance:

```bash
# Run basic evaluation on predictions:
make eval

# Run evaluation with custom run ID:
make eval RUN_ID=custom_eval_run

# Reset evaluation fields on prediction files if needed:
make reset-eval
# Can also pair that with cleaning all log files for fresh eval results:
make clean-logs
```

The evaluation process:
1. Loads predictions from the specified directory
2. Filters out already evaluated predictions
3. Runs evaluation on non-evaluated predictions
4. Updates prediction files with evaluation results
5. Generates summary statistics
6. Marks prediction files with evaluated=True and resolved status

### Available Make Commands

```bash
make install          # Install project dependencies using Poetry
make run             # Run the main prediction script to generate new predictions
make test            # Run tests using pytest
make clean           # Remove Python cache files and bytecode
make clean-repos     # Remove all cached repositories from repos directory
make clean-predictions # Remove all prediction files and old directories (asks for confirmation)
make clean-logs      # Remove all files in logs directory while preserving the directory
make format          # Format code using black
make check           # Run ruff linter with auto-fix enabled
make fix-predictions # Add missing fields to prediction files
make reset-eval      # Reset evaluation fields (resolved and evaluated) to False
make eval            # Run evaluation on predictions in ra_aid_predictions directory
make eval-post       # Run detailed post-evaluation analysis (WIP/Legacy)
make aider          # Run aider with auto-lint in current directory
```

## Repository Management

- Caches repositories in `repos/` directory (format: `repos/owner__repo/`)
- Creates one virtual environment per cached repo
- Uses git worktrees for parallel attempts:
  - Each attempt gets a unique worktree
  - Worktrees share the cached repo's virtual environment
  - Auto-cleanup after each attempt
- Fast dependency installation with `uv`:
  - Handles pyproject.toml, requirements.txt, and setup.py
  - Installs dependencies once per cached repo
  - Reuses environments across attempts

This system significantly reduces disk usage and speeds up multiple attempts by:
- Avoiding repeated cloning of repositories
- Reusing installed dependencies
- Sharing virtual environments across attempts

## Logs

SWE bench generates detailed logs during evaluation in the `logs/` directory:
- `logs/run_evaluation/<run_id>/<model>/` - Contains evaluation logs for each instance
- Each instance gets a `run_instance.log` file with:
  - Test execution output
  - Patch application results
  - Environment setup details
  - Error messages if any

## Problems/Improvements
* [ ] RA.Aid does get stuck often, multiple different errors.
  * Tool Error: Error executing code: invalid syntax (, line 4)
  * Tool Error: Error executing code: unterminated string literal (detected at line 1) (, line 1) 
  * Tool Error: Error executing code: /tmp/tmplwzqokro/sympy/sympy
  * Tool Error: Error executing code: unmatched ')' (, line 1)                                                │

* [X] Follow submission checklist with `SUBMISSION_MODE`.
* [ ] Streaming/traj file generation is fine until ra-aid inner aider starts streaming. This becomes unreadable submission guidelines require readable traj files.
* [ ] Logging setup needed.
* [ ] Fix `get_report` in report.py will allow us to get resolved status for
      each prediction file. Also gets more detail report stat information.
* [ ] Aider repomap will regenerate a repomap for each attempt, not optimal.
* [X] Shell env variables like AIDER_MODEL="openrouter/deepseek/deepseek-chat" will effect the coder model used by aider while running!
  * Fixed with os.env setting
* [ ] Add proper .env file handling and loading for API keys
* [ ] We are not calculating costs for each attempt. Need a way to extract accurate costs in predictions json then compile them in evaluation.
* [ ] Not ideal to use poetry for this projects dependencies, then use uv for problem repo dependencies. Prefer `uv` as it seems much faster.
* [ ] Post process eval needs work
  * [ ] Modify `pick_winner` method for RA.Aid, the original `choose_predictions` method doesnt work well with RA-Aid.
* [ ] Running locally with cowboy mode seems dangerous if RA.Aid can run ANY command?!
* This can get pricey $$$ quickly be careful which model you choose. I'm using deepseek/deepseek-chat for now.

## SWE Bench Submission Guidelines

https://www.swebench.com/submit.html

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
