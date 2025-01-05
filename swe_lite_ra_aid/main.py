import json
from concurrent.futures import ThreadPoolExecutor
from datasets import load_dataset
from ra_aid.agent_utils import create_agent, run_research_agent
from ra_aid.llm import initialize_llm

# Initialize the model and agent
model = initialize_llm(provider='openai', model_name='gpt-4')
agent = create_agent(model=model, tools=[])

def ra_aid_prediction(task):
    # Extract relevant information from the task
    task_description = task['prompt']
    code_context = task['context']
    
    # Combine task description and code context
    full_prompt = f"Task: {task_description}\n\nCode Context:\n{code_context}"
    
    # Use RA.Aid to generate a prediction
    result = run_research_agent(
        base_task_or_query=full_prompt,
        model=model,
        expert_enabled=True,
        research_only=True
    )
    
    # The result is already the prediction
    return result

# Function to process a single task
def process_task(task):
    # Debug print to see task structure
    print("Task keys:", task.keys())
    print("Task content:", task)
    
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
