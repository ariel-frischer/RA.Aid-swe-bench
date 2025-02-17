"""Configuration constants for RA-AID."""

from pathlib import Path

# Timeout Configuration (in seconds)
TIMEOUT = 45 * 60  # 45 minutes

# RA-AID Configuration

# Using sonnet 3.5 with openrouter should have less rate limiting issues
# RA_AID_MODEL = "anthropic/claude-3.5-sonnet"
# RA_AID_PROVIDER = "openrouter"
# RA_AID_PROVIDER = "anthropic"
# RA_AID_MODEL = "claude-3-5-sonnet-20241022"
RA_AID_PROVIDER = "openrouter"
RA_AID_MODEL = "google/gemini-2.0-flash-001"

RA_AID_FULL_MODEL = f"{RA_AID_PROVIDER}/{RA_AID_MODEL}"
# RA_AID_FULL_MODEL = "anthropic/claude-3-5-sonnet-20241022"
RA_AID_AIDER_MODEL = RA_AID_FULL_MODEL  # Use same model for aider

# RESEARCH_PROVIDER = "openrouter"
# RESEARCH_MODEL = "qwen/qwen-2.5-coder-32b-instruct"

RESEARCH_PROVIDER = "openrouter"
RESEARCH_MODEL = "google/gemini-2.0-flash-001"
# RESEARCH_PROVIDER = "openrouter"
# RESEARCH_MODEL = "allenai/llama-3.1-tulu-3-405b"

EXPERT_PROVIDER = "openrouter"
EXPERT_MODEL = "deepseek/deepseek-r1"

# Whether to stream ra-aid output to console while capturing
# Unfortunately the aider streaming portion is borked but we need to capture STDOUT for trajectory_output file generation.
# When MAX_THREADS > 1 stream will be borked
# TODO: Perhaps, disable traj/stdout capture while debugging with some configurable boolean.
STREAM_OUTPUT = True

# Directory Configuration
REPOS_DNAME = Path("repos")
PREDS_DNAME = Path("predictions")

# Processing Configuration
MAX_ATTEMPTS = 3
MAX_THREADS = 1

# Default RA-AID version if detection fails
DEFAULT_RA_AID_VERSION = "ra-aid 0.12.1"

# Submission checklist:
# https://github.com/swe-bench/experiments/blob/main/checklist.md
# When True, excludes FAIL_TO_PASS and PASS_TO_PASS test details from prompts
# Sets env variable TAVILY_API_KEY to emptry str to avoid web search
# Sets MAX_ATTEMPTS to 1, that is the submission rules: pass@1
# Final rule is to not pass the hitns, we already dont use hints in the prompt, enabled or not.
SUBMISSION_MODE = True
if SUBMISSION_MODE:
    MAX_ATTEMPTS = 1
PROCESS_CHARS = True
