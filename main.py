import json
from concurrent.futures import ThreadPoolExecutor
from swebench.harness.run_evaluation import main as run_evaluation
from swebench import swebench
from ra_aid.agent import RAAgent

# Initialize the RA.Aid agent
ra_agent = RAAgent()

def your_agent_prediction(task):
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
    prediction = your_agent_prediction(task)
    return {"id": task["id"], "prediction": prediction}

# Generate predictions for SWE-bench Lite
def generate_predictions(max_workers):
    predictions = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_task, task) for task in swebench.load_dataset("princeton-nlp/SWE-bench_Lite")]
        for future in futures:
            predictions.append(future.result())
    return predictions

# Set the number of workers
max_workers = 4

predictions = generate_predictions(max_workers)

# Save predictions to a file
predictions_path = "ra_aid_predictions.jsonl"
with open(predictions_path, "w") as f:
    for pred in predictions:
        f.write(json.dumps(pred) + "\n")

# Run evaluation
run_evaluation([
    "--dataset_name", "princeton-nlp/SWE-bench_Lite",
    "--predictions_path", predictions_path,
    "--max_workers", str(max_workers),
    "--run_id", "ra_aid_run"
])

