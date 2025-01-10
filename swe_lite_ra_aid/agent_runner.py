"""Module for handling RA-AID agent configuration and execution."""

import os
import sys
import uuid
import logging
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from ra_aid.agent_utils import run_planning_agent, run_research_agent
from ra_aid.llm import initialize_llm
from .config import RA_AID_PROVIDER, RA_AID_MODEL, STREAM_OUTPUT


def initialize_model():
    """Initialize the LLM model."""
    return initialize_llm(provider=RA_AID_PROVIDER, model_name=RA_AID_MODEL)


def get_agent_config():
    """Get configuration for research agent"""
    return {
        "expert_enabled": False,
        "hil": False,
        "web_research_enabled": True,
        "configurable": {"thread_id": str(uuid.uuid4())},
        "recursion_limit": 100,
        "research_only": True,
        "cowboy_mode": True,
    }


def run_agents(research_prompt, planning_prompt, model):
    """Run both research and planning agents with the given prompts.

    DEPRECATED: cowboy_mode config is not working properly for planner agent.
    Use uv_run_raaid() instead.
    """
    config = get_agent_config()

    # Run research agent
    research_result = run_research_agent(
        base_task_or_query=research_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        research_only=config["research_only"],
        hil=config["hil"],
        web_research_enabled=config["web_research_enabled"],
        config=config,
    )
    print(f"research_result={research_result}")

    # Run planning agent
    planning_result = run_planning_agent(
        base_task=planning_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        hil=config["hil"],
        config=config,
    )
    print(f"planning_result={planning_result}")

    return research_result, planning_result


@contextmanager
def activate_venv(repo_dir: Path):
    """
    Context manager to activate and deactivate virtual environment.
    Modifies PATH and VIRTUAL_ENV environment variables.
    """
    print(f"\nActivating venv from directory: {os.getcwd()}")
    print(f"Repo directory: {repo_dir}")

    # Use absolute path to ensure we get the correct .venv
    venv_path = (repo_dir / ".venv").resolve()
    venv_bin = venv_path / "bin"

    print(f"Resolved venv path: {venv_path}")
    print(f"Venv bin path: {venv_bin}")

    # Store original env vars
    old_path = os.environ.get("PATH", "")
    old_venv = os.environ.get("VIRTUAL_ENV")
    print(f"Original VIRTUAL_ENV: {old_venv}")

    try:
        # Modify PATH to prioritize venv
        os.environ["PATH"] = f"{venv_bin}:{old_path}"
        os.environ["VIRTUAL_ENV"] = str(venv_path)
        yield
    finally:
        # Restore original env vars
        os.environ["PATH"] = old_path
        if old_venv:
            os.environ["VIRTUAL_ENV"] = old_venv
        else:
            os.environ.pop("VIRTUAL_ENV", None)


def uv_run_raaid(repo_dir: Path, prompt: str) -> Optional[tuple[str, str]]:
    """
    Call ra-aid with the given prompt in the activated virtual environment.
    If STREAM_OUTPUT is True, streams output to console while capturing.
    Returns tuple of (trajectory_output, returncode) if successful, else None.
    """
    print("\nStarting RA.Aid...")

    cmd = [
        "ra-aid",
        "--cowboy-mode",
        "--provider",
        RA_AID_PROVIDER,
        "--model",
        RA_AID_MODEL,
        "--expert-provider",
        RA_AID_PROVIDER,
        "--expert-model",
        RA_AID_MODEL,
        "-m",
        prompt,
    ]

    output = []
    error_output = []
    current_line = []  # Buffer for building current line

    try:
        with activate_venv(repo_dir):
            if STREAM_OUTPUT:
                # Use Popen to stream and capture output
                process = subprocess.Popen(
                    cmd,
                    cwd=repo_dir,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=1,
                    universal_newlines=True,
                )

                def process_char(c):
                    if c == '\r':  # Carriage return
                        current_line.clear()
                    elif c == '\n':  # Newline
                        line = ''.join(current_line)
                        output.append(line + '\n')
                        current_line.clear()
                        print(line)  # Stream to console
                    else:
                        current_line.append(c)

                # Stream and capture stdout character by character
                while True:
                    char = process.stdout.read(1)
                    if not char:
                        break
                    process_char(char)

                # Flush any remaining content in current_line
                if current_line:
                    line = ''.join(current_line)
                    output.append(line)
                    print(line, end='')

                # Capture stderr
                for line in process.stderr:
                    print(line, end="", file=sys.stderr)
                    error_output.append(line)

                process.wait()
                returncode = process.returncode
                stdout = "".join(output)
                stderr = "".join(error_output)

                # Create a result object to match the non-streaming case
                result = type(
                    "Result",
                    (),
                    {"returncode": returncode, "stdout": stdout, "stderr": stderr},
                )()
            else:
                # Just capture output without streaming
                result = subprocess.run(
                    cmd, cwd=repo_dir, text=True, capture_output=True, check=False
                )

        print(f"Current working directory after: {os.getcwd()}")

        if not STREAM_OUTPUT:
            # Print output only if we didn't stream it
            print(stdout)
            if stderr:
                print(stderr)

        if returncode != 0:
            logging.error("ra-aid returned non-zero exit code.")
            return None
    except subprocess.TimeoutExpired:
        logging.error("ra-aid timed out")
        return None
    except Exception as e:
        logging.error(f"ra-aid error: {e}")
        return None

    trajectory_output = result.stdout + (f"\nSTDERR:\n{result.stderr}" if result.stderr else "")
    return trajectory_output, str(returncode)


def create_result_dict(
    task, model_patch, edited_files, research_result, attempt, trajectory_file=None
):
    """Create standardized result dictionary"""
    from .config import RA_AID_FULL_MODEL

    result = {
        "instance_id": task["instance_id"],
        "model_name_or_path": "ra-aid-model",
        "model_patch": model_patch + "\n" if model_patch else "",
        "edited_files": edited_files,
        "research": research_result,
        "attempt": attempt,
        "timestamp": datetime.now().isoformat(),
        "ra_aid_model": RA_AID_FULL_MODEL,
        "ra_aid_editor": RA_AID_FULL_MODEL,
        "is_winner": False,  # Default to False, will be updated by winner selection logic
    }
    if trajectory_file:
        result["trajectory_file"] = str(trajectory_file)
    return result
