"""Module for handling RA-AID agent configuration and execution."""

import uuid
from datetime import datetime
from ra_aid.agent_utils import run_planning_agent, run_research_agent
from ra_aid.llm import initialize_llm

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
    """Run both research and planning agents with the given prompts."""
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
