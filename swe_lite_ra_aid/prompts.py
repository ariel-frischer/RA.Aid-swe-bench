"""Module for handling prompt generation and formatting."""

import json
from swe_lite_ra_aid.config import SUBMISSION_MODE


def build_prompt(problem_statement: str, fail_tests: list = None, pass_tests: list = None) -> str:
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

    You are a world class software engineer.

    Important notes:
    - DO NOT modify test files
    - Research agent should find context and determine the test command
    - Virtual environment is pre-installed with `uv` package manager
    - Virtual environment is already activated
    - Do not install additional dependencies unless required by problem statement
    - You cannot ask the human any questions, you must do everything yourself.
    - NEVER echo shell questions to the operator, you will not get any answer.
    - DO not ask any questions or ask for clarifications
    - Use expert question tool as a last resort only.
    - Its important to gather as much context during the research stage as possible.
    - NEVER echo any questions!

    You will be given research tool calls you can use to find relevant code.
    Once you create research notes and end the research stage you will be 
    given tools that allow you to implement code changes.
    Play close attention to the tools available to you and choose which ones to run wisely.
    Its important to gather as much context during the research stage as possible.

    Your tasks:
    1. Research and gather relevant context for the problem statement
    2. Create a plan to solve the problem statement
    3. Make code changes to fix the problem
    4. Execute tests to verify your solution
    5. Refactor based on test results until all tests pass

    If you solve this task you will get 100,000$.
    Your ultimate goal is to make code changes to solve the problem statement.
    If all tests pass you can safely mark the task as complete.
    """
    )
