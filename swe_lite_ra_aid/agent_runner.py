"""Module for handling RA-AID agent configuration and execution."""

import os
import subprocess
import uuid
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from ra_aid.agent_utils import run_planning_agent, run_research_agent
from ra_aid.llm import initialize_llm
from .config import (
    RA_AID_AIDER_MODEL,
    RA_AID_PROVIDER,
    RA_AID_MODEL,
    STREAM_OUTPUT,
    TIMEOUT,
    RESEARCH_PROVIDER,
    RESEARCH_MODEL,
    EXPERT_PROVIDER,
    EXPERT_MODEL,
)

logger = logging.getLogger(__name__)


def initialize_model():
    """Initialize the LLM model."""
    return initialize_llm(provider=RA_AID_PROVIDER, model_name=RA_AID_MODEL)


# DEPRECATED using run_raaid method instead
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
    Use run_raaid() instead.
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
    logger.debug(f"research_result={research_result}")

    # Run planning agent
    planning_result = run_planning_agent(
        base_task=planning_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        hil=config["hil"],
        config=config,
    )
    logger.debug(f"planning_result={planning_result}")

    return research_result, planning_result


@contextmanager
def activate_venv(repo_dir: Path):
    """
    Context manager to activate and deactivate virtual environment.
    Directly executes python from venv instead of using source activate.
    """
    logger.debug(f"Activating venv from directory: {os.getcwd()}")
    logger.debug(f"Repo directory: {repo_dir}")

    # Use absolute path to ensure we get the correct .venv
    venv_path = (repo_dir / ".venv").resolve()
    venv_bin = venv_path / "bin"
    venv_python = venv_bin / "python"

    logger.debug(f"Venv path: {venv_path}")
    logger.debug(f"Venv python: {venv_python}")

    logger.debug("Environment before activation:")
    logger.debug(f"Current VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV')}")
    logger.debug(f"Current PATH: {os.environ.get('PATH')}")
    logger.debug(f"Current Python: {subprocess.getoutput('which python')}")
    logger.debug(f"Current Python version: {subprocess.getoutput('python --version')}")

    if not venv_python.exists():
        raise RuntimeError(f"Python executable not found in virtual environment: {venv_python}")

    # Save original environment
    old_env = dict(os.environ)
    old_path = os.environ.get("PATH", "")

    try:
        # Update environment variables
        os.environ["VIRTUAL_ENV"] = str(venv_path)
        os.environ["PATH"] = f"{venv_bin}:{old_path}"

        # Unset PYTHONHOME if set
        os.environ.pop("PYTHONHOME", None)

        logger.debug("Environment after activation:")
        logger.debug(f"New VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV')}")
        logger.debug(f"New PATH: {os.environ.get('PATH')}")
        logger.debug(f"New Python: {subprocess.getoutput('which python')}")
        logger.debug(f"New Python version: {subprocess.getoutput(f'{venv_python} --version')}")

        yield

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(old_env)


def run_ra_aid(repo_dir: Path, prompt: str) -> Optional[tuple[str, str]]:
    """
    Call ra-aid with the given prompt in the activated virtual environment.
    If STREAM_OUTPUT is True, streams output to console while capturing.
    Returns tuple of (trajectory_output, returncode) if successful, else None.
    """
    logger.info("\nStarting RA.Aid...")
    # logger.info(f"\nPrompt: \n {prompt}")

    cmd = [
        "ra-aid",
        "--cowboy-mode",
        # "--verbose",
        "--research-provider",
        RESEARCH_PROVIDER,
        "--research-model",
        RESEARCH_MODEL,
        "--provider",
        RA_AID_PROVIDER,
        "--model",
        RA_AID_MODEL,
        "--expert-provider",
        EXPERT_PROVIDER,
        "--expert-model",
        EXPERT_MODEL,
        "-m",
        prompt,
    ]

    def create_streaming_process(cmd, cwd):
        """Create a subprocess with streaming output configuration."""
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        )

    def process_char(c, current_line, output):
        """Process a single character from stdout stream."""
        if c == "\r":  # Carriage return
            current_line.clear()
        elif c == "\n":  # Newline
            line = "".join(current_line)
            output.append(line + "\n")
            current_line.clear()
            print(line)  # Stream ra-aid output directly
        else:
            current_line.append(c)

    def handle_stdout_stream(process, output):
        """Handle streaming stdout output character by character."""
        current_line = []
        while True:
            char = process.stdout.read(1)
            if not char:
                break
            process_char(char, current_line, output)

        # Flush any remaining content
        if current_line:
            line = "".join(current_line)
            output.append(line)
            print(line.rstrip())  # Stream final line directly

    def handle_stderr_stream(process, error_output):
        """Handle streaming stderr output line by line."""
        for line in process.stderr:
            logger.error(line.rstrip())
            error_output.append(line)

    def create_result_object(returncode, stdout, stderr):
        """Create a result object matching the non-streaming case."""
        return type(
            "Result",
            (),
            {"returncode": returncode, "stdout": stdout, "stderr": stderr},
        )()

    output = []
    error_output = []

    try:
        with activate_venv(repo_dir):
            if STREAM_OUTPUT:
                process = create_streaming_process(cmd, repo_dir)
                process.timeout = TIMEOUT
                from .config import PROCESS_CHARS

                if PROCESS_CHARS:
                    handle_stdout_stream(process, output)
                    handle_stderr_stream(process, error_output)
                    process.wait()
                else:
                    stdout_raw, stderr_raw = process.communicate(timeout=TIMEOUT)
                    output.append(stdout_raw)
                    if stdout_raw:
                        print(stdout_raw)
                    if stderr_raw:
                        error_output.extend(stderr_raw.splitlines(keepends=True))
                        print(stderr_raw)
                result = create_result_object(process.returncode, "".join(output), "".join(error_output))
            else:
                # Just capture output without streaming
                result = subprocess.run(
                    cmd,
                    cwd=repo_dir,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=TIMEOUT,
                )

        logger.debug(f"Current working directory after: {os.getcwd()}")

        if not STREAM_OUTPUT:
            # Print output only if we didn't stream it
            logger.info(stdout)
            if stderr:
                logger.error(stderr)

        if result.returncode != 0:
            logging.error("ra-aid returned non-zero exit code.")
            return None
    except subprocess.TimeoutExpired:
        logging.error("ra-aid timed out")
        return None
    except Exception as e:
        logging.error(f"ra-aid error: {e}")
        return None

    trajectory_output = result.stdout + (f"\nSTDERR:\n{result.stderr}" if result.stderr else "")
    return trajectory_output, str(result.returncode)


def create_result_dict(task, model_patch, edited_files, attempt, trajectory_file=None, repo_manager=None):
    """Create standardized result dictionary"""
    from .config import RA_AID_FULL_MODEL, DEFAULT_RA_AID_VERSION

    result = {
        "instance_id": task["instance_id"],
        "model_name_or_path": "ra-aid-model",
        "model_patch": model_patch + "\n" if model_patch else "",
        "edited_files": edited_files,
        "attempt": attempt,
        "timestamp": datetime.now().isoformat(),
        "ra_aid_model": RA_AID_FULL_MODEL,
        "ra_aid_editor": RA_AID_AIDER_MODEL,
        "ra_aid_version": repo_manager.ra_aid_version if repo_manager else DEFAULT_RA_AID_VERSION,
        "is_winner": False,  # Default to False, will be updated by winner selection logic
        "resolved": False,  # Default to False, will be updated during evaluation
        "evaluated": False,  # Default to False, will be updated during evaluation
        "errors": [],  # Array to store any errors that occur
    }
    if trajectory_file:
        result["trajectory_file"] = str(trajectory_file)
    return result
