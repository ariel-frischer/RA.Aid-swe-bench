import json
import uuid
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from git import Repo
from datasets import load_dataset
from ra_aid.agent_utils import (
    run_research_agent,
    run_planning_agent,
    run_task_implementation_agent,
)
from ra_aid.llm import initialize_llm

# Initialize the model
model = initialize_llm(provider="openrouter", model_name="deepseek/deepseek-chat")


def ra_aid_prediction(task):
    # Extract relevant information from the task
    problem_statement = task["problem_statement"]
    repo = task["repo"]
    base_commit = task["base_commit"]
    patch = task["patch"]
    test_patch = task["test_patch"]
    hints = task.get("hints_text", "")  # Optional field

    # Combine all relevant information into a comprehensive prompt
    full_prompt = f"""
    Repository: {repo}
    Problem Statement: {problem_statement}
    Base Commit: {base_commit}

    Code Changes (Patch):
    {patch}

    Test Changes:
    {test_patch}

    Additional Hints:
    {hints}
    """
    print(f"full_prompt={full_prompt}")

    # Setup configuration
    config = {
        "expert_enabled": False,
        "hil": False,
        "web_research_enabled": True,
        "configurable": {"thread_id": str(uuid.uuid4())},
        "recursion_limit": 100,
        "research_only": False,
        "cowboy_mode": False,
    }

    # Run research stage
    research_result = run_research_agent(
        base_task_or_query=full_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        research_only=config["research_only"],
        hil=config["hil"],
        web_research_enabled=config["web_research_enabled"],
        config=config,
    )

    # Run planning stage
    planning_result = run_planning_agent(
        base_task=full_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        hil=config["hil"],
        config=config,
    )

    # Run implementation stage
    implementation_result = run_task_implementation_agent(
        base_task=full_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        hil=config["hil"],
        config=config,
    )

    # Combine results from all stages
    combined_result = {
        "research": research_result,
        "planning": planning_result,
        "implementation": implementation_result,
    }

    return combined_result


# Function to process a single task
def clone_repository(repo_name):
    """Clone a GitHub repository and return the local path"""
    repo_url = f"https://github.com/{repo_name}.git"
    clone_dir = f"repos/{repo_name.replace('/', '_')}"

    # Create repos directory if it doesn't exist
    os.makedirs("repos", exist_ok=True)

    # Only clone if directory doesn't exist
    if not os.path.exists(clone_dir):
        print(f"Cloning repository: {repo_url}")
        Repo.clone_from(repo_url, clone_dir)
    else:
        print(f"Using existing repository: {clone_dir}")

    return clone_dir


def process_task(task):
    # Handle both dict and string input
    if isinstance(task, str):
        try:
            task = json.loads(task)
        except json.JSONDecodeError:
            # If it's not valid JSON, treat as raw string
            task = {"raw_input": task}
    
    # Debug print to see task structure
    print(f"\nProcessing task {task.get('instance_id', 'unknown')} from {task.get('repo', 'unknown')}")
    print("Task keys:", list(task.keys()))

    # Clone the repository
    repo_path = clone_repository(task.get("repo"))
    print(f"Using repository at: {repo_path}")

    try:
        # Change to the cloned repository directory
        original_dir = os.getcwd()
        os.chdir(repo_path)

        # Checkout the base commit
        repo = Repo(repo_path)
        repo.git.checkout(task["base_commit"])

        # Run prediction
        prediction = ra_aid_prediction(task)

        # Return to original directory
        os.chdir(original_dir)

        return {"id": task["id"], "prediction": prediction}

    finally:
        # Just return to original directory, don't clean up
        os.chdir(original_dir)


# Generate predictions for SWE-bench Lite
def generate_predictions(dataset, max_workers):
    predictions = []
    # Take only first 3 tasks for debugging
    limited_dataset = list(dataset)[:3]
    print(f"Processing {len(limited_dataset)} tasks")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_task, task) for task in limited_dataset]
        for i, future in enumerate(futures):
            print(f"Processing task {i+1}/{len(limited_dataset)}")
            predictions.append(future.result())
    return predictions


def main():
    # Load the dataset
    dataset = load_dataset("princeton-nlp/SWE-bench", split="test")

    # Set the number of workers
    max_workers = 1

    predictions = generate_predictions(dataset, max_workers)

    # Save predictions to a file
    predictions_path = "ra_aid_predictions.jsonl"
    with open(predictions_path, "w") as f:
        for pred in predictions:
            f.write(json.dumps(pred) + "\n")

    print(f"Predictions saved to {predictions_path}")

    # Note: The evaluation part has been removed as it relied on swebench.
    # You may need to implement a custom evaluation function or use a different evaluation method.


if __name__ == "__main__":
    main()
