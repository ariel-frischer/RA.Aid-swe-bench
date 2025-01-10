import datetime
import json
import shutil
from pathlib import Path

from datasets import load_dataset

from .dump import dump  # noqa: F401

FULL_DATASET = "princeton-nlp/SWE-bench"
FULL_DATASET_FNAME = FULL_DATASET.replace("/", "--") + ".json"

LITE_DATASET = "princeton-nlp/SWE-bench_Lite"
LITE_DATASET_FNAME = LITE_DATASET.replace("/", "--") + ".json"


def dump_dataset(dataset, fname):
    entries = list(dataset)
    for entry in entries:
        entry["FAIL_TO_PASS"] = json.loads(entry["FAIL_TO_PASS"])
        entry["PASS_TO_PASS"] = json.loads(entry["PASS_TO_PASS"])

    with open(fname, "w") as f:
        json.dump(entries, f, indent=4)


def get_full_dataset():
    """
    Load the full SWE-bench dataset.

    Returns:
        dict: Dataset entries keyed by instance_id
    """
    return get_dataset(FULL_DATASET, FULL_DATASET_FNAME)


def get_lite_dataset():
    """
    Load the SWE-bench Lite dataset.

    Returns:
        dict: Dataset entries keyed by instance_id
    """
    return get_dataset(LITE_DATASET, LITE_DATASET_FNAME)


def get_dataset(dataset, fname):

    fname = Path(fname)
    if fname.exists():
        dataset = json.loads(fname.read_text())
    else:
        dump(dataset)
        dataset = load_dataset(dataset)
        dataset = dataset["test"]
        dump_dataset(dataset, fname)

    res = dict()
    for entry in dataset:
        res[entry["instance_id"]] = entry

    return res


def load_predictions(paths):
    prediction_paths = []
    for path in paths:
        path = Path(path)
        if path.is_file():
            prediction_paths.append(path)
        elif path.is_dir():
            prediction_paths += list(path.glob("*.json"))
        else:
            assert False, path

    # prediction_paths.sort(key=lambda p: p.stat().st_mtime)

    predictions = dict()
    for fname in prediction_paths:
        try:
            pred = json.loads(fname.read_text())
        except json.decoder.JSONDecodeError as err:
            dump(fname)
            raise err

        if "instance_id" not in pred:
            print("Skipping json without instance_id", fname)
            continue

        inst = pred["instance_id"]
        pred["json_fname"] = str(fname)
        predictions[inst] = pred


    return predictions


def is_plausible(pred):
    """
    Check if a prediction result is plausible.

    Args:
        pred (dict): Prediction result dictionary

    Returns:
        bool: True if prediction has valid model_patch and edited_files
    """
    if not pred.get("model_patch"):
        return False
    if not pred.get("edited_files"):
        return False
    return True


def get_plausible(preds):
    """
    Get set of instance IDs with plausible predictions.

    Args:
        preds (dict): Predictions dictionary

    Returns:
        set: Instance IDs that have plausible predictions
    """
    return set(inst for inst, pred in preds.items() if is_plausible(pred))


def check_criteria(pred, criteria):
    """
    Check if prediction meets specified criteria.

    Args:
        pred (dict): Prediction dictionary
        criteria (str): Space-separated string of required attributes

    Returns:
        bool: True if prediction has all required attributes with truthy values
    """
    attrs = criteria.split()
    for attr in attrs:
        if not pred[attr]:
            return False
    return True


def pick_winner_aider(results):
    """
    Legacy winner selection using Aider's criteria including edit/lint/test outcomes.
    Kept for reference but no longer used.
    """
    priority = (
        "model_patch edit_outcome lint_outcome test_outcome",  # all good!
        "model_patch edit_outcome lint_outcome",  # all good but test_outcome
        "model_patch lint_outcome",  # a patch that lints?
        "model_patch edit_outcome",  # a patch that had no edit errors?
        "model_patch",  # anything with an actual patch!
    )

    # choose the best result available
    for criteria in priority:
        for res in results:
            if check_criteria(res, criteria):
                return res

    # choose the first result as a last resort
    if results:
        return results[0]

def deprecated_pick_winner(results):
    """
    Select best prediction from multiple results based on model_patch and edited_files.
    
    DEPRECATED: Use pick_winner() instead which selects based on is_winner flag.

    Args:
        results (list): List of prediction results

    Returns:
        dict: Best prediction based on number of edited files, or first result if none have edits
    """
    # First try to find results with both model_patch and edited_files
    valid_results = [r for r in results if r.get("model_patch") and r.get("edited_files")]
    
    if valid_results:
        # Return the result with the most edited files
        return max(valid_results, key=lambda r: len(r.get("edited_files", [])))
    
    # If no results have both, try to find any with just a model_patch
    patch_results = [r for r in results if r.get("model_patch")]
    if patch_results:
        return patch_results[0]
        
    # Last resort - return first result if any exist
    return results[0] if results else None




def pick_winner(results):
    """
    Select best prediction from multiple results based on is_winner flag.

    Args:
        results (list): List of prediction results

    Returns:
        dict: First prediction marked with is_winner=True, or first result if none are winners
    """
    # First try to find results marked as winners
    winners = [r for r in results if r.get("is_winner", False)]
    if winners:
        return winners[0]
    
    # Last resort - return first result if any exist
    return results[0] if results else None

def old(fname):
    """
    Move a file to an OLD subdirectory with timestamp.

    Args:
        fname (Path): Path to file to be moved

    Creates OLD subdirectory if it doesn't exist.
    Renames file to include timestamp in format YYMMDD-HHMMSS.
    """
    fname = Path(fname)
    if not fname.exists():
        return

    old_dname = fname.parent / "OLD"
    old_dname.mkdir(exist_ok=True)

    now = datetime.datetime.today()
    now = now.strftime("%y%m%d-%H%M%S")
    to = old_dname / f"{fname.name}.{now}"

    print(to, fname)

    fname.rename(to)


def choose_pred(inst, all_preds, dnames):
    """
    Choose best prediction for an instance from multiple prediction sets.

    Args:
        inst (str): Instance ID
        all_preds (list): List of prediction dictionaries
        dnames (list): List of directory names corresponding to predictions

    Returns:
        dict: Best prediction for the instance, with added dname field
    """
    results = []
    for i in range(len(all_preds)):
        preds = all_preds[i]
        dname = dnames[i]

        if inst not in preds:
            # print(f"skipping: inst not in preds for {inst}")
            continue
        pred = dict(preds[inst])
        pred["dname"] = Path(dname).name
        results.append(pred)

    return pick_winner(results)


def choose_predictions(dnames, model_name_or_path=None, copy_md=False):
    all_preds = [load_predictions([dname]) for dname in dnames]
    all_instances = set()
    for preds in all_preds:
        all_instances.update(preds.keys())

    chosen = dict()
    for inst in all_instances:
        res = choose_pred(inst, all_preds, dnames)
        chosen[inst] = res

        if copy_md:
            pred_dname = Path("predictions")
            md_fname = pred_dname / res["dname"] / (inst + ".md")
            if md_fname.exists():
                new_md_fname = pred_dname / model_name_or_path / (inst + ".md")
                shutil.copyfile(md_fname, new_md_fname)

    for inst in chosen:
        pred = dict(chosen[inst])
        pred["model_name_or_path"] = model_name_or_path
        chosen[inst] = pred

    dump(len(chosen))
    return chosen
