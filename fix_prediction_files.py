#!/usr/bin/env python
import json
from pathlib import Path
from datetime import datetime


def fix_prediction_files():
    "Had missing fields on prediction files, you can use this method to update them"

    predictions_dir = Path("predictions/ra_aid_predictions")

    for json_file in predictions_dir.glob("*.json"):
        data = json.loads(json_file.read_text())

        # Add required fields if not present
        modified = False
        if "model_name_or_path" not in data:
            data["model_name_or_path"] = "ra-aid-model"
            modified = True

        if "timestamp" not in data:
            data["timestamp"] = datetime.now().isoformat()
            modified = True

        if "ra_aid_model" not in data:
            data["ra_aid_model"] = "openrouter/deepseek/deepseek-chat"
            modified = True

        if "ra_aid_editor" not in data:
            data["ra_aid_editor"] = "anthropic/claude-3-5-sonnet-20241022"
            modified = True
            
        if "resolved" not in data:
            data["resolved"] = False
            modified = True

        if modified:
            json_file.write_text(json.dumps(data, indent=4))
            print(f"Updated {json_file}")


if __name__ == "__main__":
    fix_prediction_files()
