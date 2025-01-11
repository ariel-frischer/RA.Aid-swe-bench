#!/usr/bin/env python
"""
Fix or reset prediction file fields.

Usage:
    poetry run python fix_prediction_files.py  # Add missing fields
    poetry run python fix_prediction_files.py --reset-eval  # Reset evaluation fields
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def reset_evaluation_fields(json_file, data):
    """Reset evaluation fields in prediction data to False.
    
    Args:
        json_file (Path): Path to the JSON file
        data (dict): Prediction data dictionary
        
    Returns:
        bool: True if fields were modified
    """
    modified = False
    data["resolved"] = False
    data["evaluated"] = False
    modified = True
    print(f"Reset evaluation fields for {json_file}")
    return modified


def fix_prediction_files(reset_eval=False):
    """
    Fix prediction files by adding missing fields or resetting evaluation status.
    
    Args:
        reset_eval (bool): If True, reset evaluation fields to False
    """
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

        # Reset evaluation fields if requested
        if reset_eval:
            modified = reset_evaluation_fields(json_file, data) or modified

        if modified:
            json_file.write_text(json.dumps(data, indent=4))
            print(f"Updated {json_file}")


def main():
    parser = argparse.ArgumentParser(description="Fix or reset prediction file fields")
    parser.add_argument("--reset-eval", action="store_true",
                       help="Reset evaluation fields (resolved and evaluated) to False")
    
    args = parser.parse_args()
    fix_prediction_files(reset_eval=args.reset_eval)


if __name__ == "__main__":
    main()
