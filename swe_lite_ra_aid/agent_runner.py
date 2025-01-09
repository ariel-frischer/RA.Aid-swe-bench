"""Module for handling RA-AID agent configuration and execution."""

import uuid
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from ra_aid.agent_utils import run_planning_agent, run_research_agent
from ra_aid.llm import initialize_llm
from .git import get_git_patch

def initialize_model():
    """Initialize the LLM model."""
    return initialize_llm(provider="openrouter", model_name="deepseek/deepseek-chat")

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

def uv_run_raaid(repo_dir: Path, prompt: str) -> Optional[str]:
    """
    Call 'uv run ra-aid' with the given prompt in the environment,
    streaming output directly to the console (capture_output=False).
    Returns the patch if successful, else None.
    """
    cmd = [
        "uv", "run", "ra-aid",
        "--cowboy-mode",
        "-m", prompt
    ]
    # We are NOT capturing output, so it streams live:
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_dir,
            text=True,
            check=False,   # We manually handle exit code
        )
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
        "ra_aid_model": "openrouter/deepseek/deepseek-chat",
        "ra_aid_editor": "openrouter/deepseek/deepseek-chat",
    }
