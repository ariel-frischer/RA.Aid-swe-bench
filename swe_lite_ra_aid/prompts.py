"""Module for handling prompt generation and formatting."""

import json

def build_prompt(problem_statement: str, fail_tests: list, pass_tests: list) -> str:
    """Construct the prompt text from problem_statement, FAIL_TO_PASS, PASS_TO_PASS."""
    prompt = f"{problem_statement}\n\nTests that need to be fixed:\n```\n"
    for t in fail_tests:
        prompt += f"- {t}\n"
    prompt += "```\n\n"
    if pass_tests:
        prompt += "Tests that must remain passing:\n```\n"
        for t in pass_tests:
            prompt += f"- {t}\n"
        prompt += "```\n\n"
    prompt += "\n\nYou must run all above tests both **before and after** making changes, and ensure they pass as you do your work. Do not write any new test cases."
    return prompt

def prepare_base_prompt(task):
    """Prepare the common base prompt used by both agents"""
    fail_tests = json.loads(task["FAIL_TO_PASS"])
    pass_tests = json.loads(task["PASS_TO_PASS"])

    problem_details = build_prompt(task["problem_statement"], fail_tests, pass_tests)

    return f"""
    Repository: {task["repo"]}

    Base Commit: {task["base_commit"]}
    Code Changes (Patch):
    {task["patch"]}

    Test Changes:
    {task["test_patch"]}

    <Problem Statement and Tests>:
    {problem_details}
    </Problem Statement and Tests>

    Additional Hints:
    {task.get("hints_text", "")}"""

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
    You must make code changes to fix the issue described in the problem statement.
    """
    )
