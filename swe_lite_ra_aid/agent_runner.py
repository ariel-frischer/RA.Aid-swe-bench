"""Module for handling RA-AID agent configuration and execution."""

import os
import uuid
import logging
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from ra_aid.agent_utils import run_planning_agent, run_research_agent
from ra_aid.llm import initialize_llm
from .git import get_git_patch

def initialize_model():
    """Initialize the LLM model."""
    from swe_lite_ra_aid.main import RA_AID_PROVIDER, RA_AID_MODEL
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
    venv_path = repo_dir / ".venv"
    venv_bin = venv_path / "bin"
    
    # Store original env vars
    old_path = os.environ.get("PATH", "")
    old_venv = os.environ.get("VIRTUAL_ENV")
    
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

def uv_run_raaid(repo_dir: Path, prompt: str) -> Optional[str]:
    """
    Call ra-aid with the given prompt in the activated virtual environment,
    streaming output directly to the console (capture_output=False).
    Returns the patch if successful, else None.
    """
    print(f"\nStarting RA.Aid in directory: {repo_dir}")
    print(f"Current working directory before: {os.getcwd()}")
    
    from swe_lite_ra_aid.main import RA_AID_PROVIDER, RA_AID_MODEL
    cmd = [
        "ra-aid",
        "--cowboy-mode",
        "--provider", RA_AID_PROVIDER,
        "--model", RA_AID_MODEL,
        "-m", prompt
    ]
    
    # print(f"Full command: {' '.join(cmd)}")
    
    # We are NOT capturing output, so it streams live:
    try:
        with activate_venv(repo_dir):
            result = subprocess.run(
                cmd,
                cwd=repo_dir,
                text=True,
                check=False,   # We manually handle exit code
            )
        print(f"Current working directory after: {os.getcwd()}")
        if result.returncode != 0:
            logging.error("ra-aid returned non-zero exit code.")
            return None
    except subprocess.TimeoutExpired:
        logging.error("ra-aid timed out")
        return None
    except Exception as e:
        logging.error(f"ra-aid error: {e}")
        return None

    # Collect patch
    patch = get_git_patch(repo_dir)
    return patch


def create_result_dict(task, model_patch, edited_files, research_result, attempt):
    """Create standardized result dictionary"""
    return {
        "instance_id": task["instance_id"],
        "model_name_or_path": "ra-aid-model",
        "model_patch": model_patch + "\n" if model_patch else "",
        "edited_files": edited_files,
        "research": research_result,
        "attempt": attempt,
        "timestamp": datetime.now().isoformat(),
        "ra_aid_model": RA_AID_FULL_MODEL,
        "ra_aid_editor": RA_AID_FULL_MODEL,
    }
