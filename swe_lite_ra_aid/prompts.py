"""Module for handling prompt generation and formatting."""

import json
from swe_lite_ra_aid.config import SUBMISSION_MODE


def build_prompt(
    problem_statement: str, fail_tests: list = None, pass_tests: list = None
) -> str:
    """Construct the prompt text from problem_statement, and optionally FAIL_TO_PASS, PASS_TO_PASS."""
    prompt = f"{problem_statement}\n\n"

    if not SUBMISSION_MODE:
        if fail_tests:
            prompt += "Tests that need to be fixed:\n```\n"
            for t in fail_tests:
                prompt += f"- {t}\n"
            prompt += "```\n\n"

        if pass_tests:
            prompt += "Tests that must remain passing:\n```\n"
            for t in pass_tests:
                prompt += f"- {t}\n"
            prompt += "```\n\n"

        prompt += "\n\nYou must run all tests both **before and after** making changes, and ensure they pass as you do your work. Do not write any new test cases."
    return prompt


def prepare_base_prompt(task):
    """Prepare the common base prompt used by both agents"""

    if not SUBMISSION_MODE:
        fail_tests = json.loads(task["FAIL_TO_PASS"])
        pass_tests = json.loads(task["PASS_TO_PASS"])
    else:
        fail_tests = None
        pass_tests = None

    problem_details = build_prompt(task["problem_statement"], fail_tests, pass_tests)

    return f"""
    Repository: {task["repo"]}

    Base Commit: {task["base_commit"]}
    Code Changes (Patch):
    {task["patch"]}

    Test Changes:
    {task["test_patch"]}

    <Problem Statement>:
    {problem_details}
    </Problem Statement>

    """


def prepare_research_prompt(task):
    """Prepare the prompt specifically for the research agent"""
    base_prompt = prepare_base_prompt(task)
    return (
        base_prompt
        + """

    You are a research assistant tasked with finding all relevant context and information needed to solve this issue.
    You must be comprehensive and thorough in gathering information about the codebase, related issues, and potential solutions.
    """
    )


def prepare_planning_prompt(task):
    """Prepare the prompt specifically for the planning agent"""
    base_prompt = prepare_base_prompt(task)
    return (
        base_prompt
        + """

    You are a world class software engineer. Given the problem statement you will first do some research to gather relevant context
    then you must make code changes to fix the problem. Do not modify test files. Research agent should find context for the problem 
    statement and determine what the test command is for the given repository. The virtual environment has already been pre-installed automatically
    with the `uv` package manager, and the virtual environment is activated. You should never install additional dependencies unless it is 
    part of the problem statement.
    Execute tests to determine if you have solved the problem statement.
    """
    )
