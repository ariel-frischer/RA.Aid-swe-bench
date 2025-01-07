#!/usr/bin/env python
import json
from pathlib import Path

def add_model_name():
    predictions_dir = Path("predictions/ra_aid_predictions")
    
    for json_file in predictions_dir.glob("*.json"):
        # Read existing JSON
        data = json.loads(json_file.read_text())
        
        # Add model_name_or_path if not present
        if "model_name_or_path" not in data:
            data["model_name_or_path"] = "ra-aid-model"
            
            # Write back to file
            json_file.write_text(json.dumps(data, indent=4))
            print(f"Updated {json_file}")

if __name__ == "__main__":
    add_model_name()
