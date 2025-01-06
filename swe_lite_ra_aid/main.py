import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datasets import load_dataset
from ra_aid.agent_utils import (
    create_agent,
    run_research_agent,
    run_planning_agent,
    run_task_implementation_agent
)
from ra_aid.llm import initialize_llm
from ra_aid.tools.memory import MemorySaver

# Initialize the model
model = initialize_llm(provider='openai', model_name='gpt-4')

def ra_aid_prediction(task):
    # Extract relevant information from the task
    problem_statement = task['problem_statement']
    repo = task['repo']
    base_commit = task['base_commit']
    patch = task['patch']
    test_patch = task['test_patch']
    hints = task.get('hints_text', '')  # Optional field
    
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
    
    # Setup configuration
    config = {
        "expert_enabled": True,
        "hil": False,
        "web_research_enabled": True,
        "configurable": {"thread_id": str(uuid.uuid4())},
        "recursion_limit": 100,
        "research_only": False,
        "cowboy_mode": False
    }

    # Setup memory
    memory = MemorySaver()

    # Run research stage
    research_result = run_research_agent(
        base_task_or_query=full_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        research_only=config["research_only"],
        hil=config["hil"],
        web_research_enabled=config["web_research_enabled"],
        memory=memory,
        config=config
    )

    # Run planning stage
    planning_result = run_planning_agent(
        base_task=full_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        hil=config["hil"],
        memory=memory,
        config=config
    )

    # Run implementation stage
    implementation_result = run_task_implementation_agent(
        base_task=full_prompt,
        model=model,
        expert_enabled=config["expert_enabled"],
        hil=config["hil"],
        memory=memory,
        config=config
    )

    # Combine results from all stages
    combined_result = {
        "research": research_result,
        "planning": planning_result,
        "implementation": implementation_result
    }
    
    return combined_result

# Function to process a single task
def process_task(task):
    # Debug print to see task structure
    print("Task keys:", task.keys())
    # print("Task content:", task)
    
    prediction = ra_aid_prediction(task)
    return {"id": task["id"], "prediction": prediction}

# Generate predictions for SWE-bench Lite
def generate_predictions(dataset, max_workers):
    predictions = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_task, task) for task in dataset]
        for future in futures:
            predictions.append(future.result())
    return predictions

# Load the dataset
dataset = load_dataset('princeton-nlp/SWE-bench', split='test')

# Set the number of workers
max_workers = 4

predictions = generate_predictions(dataset, max_workers)

# Save predictions to a file
predictions_path = "ra_aid_predictions.jsonl"
with open(predictions_path, "w") as f:
    for pred in predictions:
        f.write(json.dumps(pred) + "\n")

print(f"Predictions saved to {predictions_path}")

# Note: The evaluation part has been removed as it relied on swebench.
# You may need to implement a custom evaluation function or use a different evaluation method.
