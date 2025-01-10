"""Configuration constants for RA-AID."""
from pathlib import Path

# RA-AID Configuration
RA_AID_PROVIDER = "openrouter"
RA_AID_MODEL = "deepseek/deepseek-chat"
RA_AID_FULL_MODEL = f"{RA_AID_PROVIDER}/{RA_AID_MODEL}"
RA_AID_AIDER_MODEL = RA_AID_FULL_MODEL  # Use same model for aider

# Output Configuration
STREAM_OUTPUT = True  # Whether to stream ra-aid output to console while capturing

# Directory Configuration
REPOS_DNAME = Path("repos")
PREDS_DNAME = Path("predictions")

# Processing Configuration
MAX_ATTEMPTS = 3
MAX_THREADS = 1

# Submission checklist:
# https://github.com/swe-bench/experiments/blob/main/checklist.md
# When True, excludes FAIL_TO_PASS and PASS_TO_PASS test details from prompts
# Sets env variable TAVILY_API_KEY to emptry str to avoid web search
# Sets MAX_ATTEMPTS to 1, that is the submission rules: pass@1
# We already dont use hints in prompt, enabled or not.
SUBMISSION_MODE = True
if SUBMISSION_MODE:
    MAX_ATTEMPTS = 1
