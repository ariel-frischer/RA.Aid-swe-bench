import json
from concurrent.futures import ThreadPoolExecutor
from datasets import load_dataset
from ra_aid.agent import RAAgent

# Initialize the RA.Aid agent
ra_agent = RAAgent()

def ra_aid_prediction(task):
    # Extract relevant information from the task
    task_description = task['prompt']
    code_context = task['context']
    
    # Combine task description and code context
    full_prompt = f"Task: {task_description}\n\nCode Context:\n{code_context}"
    
    # Use RA.Aid to generate a prediction
    response = ra_agent.run(full_prompt)
    
    # Extract the relevant part of the response (assuming it's the last message)
    prediction = response['messages'][-1]['content']
    
    return prediction

# Function to process a single task
def process_task(task):
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
