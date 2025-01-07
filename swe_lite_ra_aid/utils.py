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
    """
    Save the dataset to a JSON file.

    Args:
        dataset: The dataset object to save
        fname: Path to the output JSON file

    The function converts FAIL_TO_PASS and PASS_TO_PASS fields from string to JSON.
    """
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
    """
    Load a dataset from Hugging Face and cache it locally.

    Args:
        dataset (str): Hugging Face dataset identifier
        fname (str): Local cache filename

    Returns:
        dict: Dataset entries keyed by instance_id

    The function loads the dataset from Hugging Face if not cached,
    otherwise loads from the local JSON cache file.
    """

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


def load_predictions(paths, devin_only=False):
    """
    Load model predictions from JSON files.

    Args:
        paths (list): List of file/directory paths containing prediction JSONs
        devin_only (bool): If True, only load predictions for Devin instances

    Returns:
        dict: Predictions keyed by instance_id

    Loads predictions from individual JSON files or directories of JSON files.
    Each prediction must have an instance_id field.
    """
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

    if devin_only:
        predictions = filter_preds_by_devin(predictions)

    return predictions


def is_plausible(pred):
    """
    Check if a prediction result is plausible.

    Args:
        pred (dict): Prediction result dictionary

    Returns:
        bool: True if prediction has valid model_patch, edit_outcome,
              lint_outcome and test_outcome, False otherwise
    """
    attrs = "model_patch edit_outcome lint_outcome test_outcome".split()
    for attr in attrs:
        if not pred.get(attr):
            return
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


def pick_winner(results):
    """
    Select best prediction from multiple results.

    Args:
        results (list): List of prediction results

    Returns:
        dict: Best prediction based on priority criteria, or first result if none meet criteria

    Tries increasingly weaker criteria to find the strongest available result:
    1. All outcomes good (model_patch, edit_outcome, lint_outcome, test_outcome)
    2. All good except test_outcome
    3. Has model_patch and lint_outcome
    4. Has model_patch and edit_outcome
    5. Has any model_patch
    6. First result as fallback
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


def get_devin_instance_ids():
    """
    Get set of instance IDs from Devin benchmark results.

    Returns:
        set: Instance IDs from Devin benchmark output diffs
    """
    dname = Path("devin-swebench-results/output_diffs")

    ids = [fname for fname in dname.glob("*/*.txt")]

    suffix = "-diff.txt"
    for iid in ids:
        assert iid.name.endswith(suffix)

    ids = set(iid.name[: -len(suffix)] for iid in ids)

    print("devin ids", len(ids))
    return ids


def filter_preds_by_devin(predictions):
    """
    Filter predictions to only include Devin benchmark instances.

    Args:
        predictions (dict): Full predictions dictionary

    Returns:
        dict: Filtered predictions containing only Devin instances
    """
    devin_insts = get_devin_instance_ids()
    predictions = dict((inst, pred) for (inst, pred) in predictions.items() if inst in devin_insts)
    return predictions


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
            continue
        pred = dict(preds[inst])
        pred["dname"] = Path(dname).name
        results.append(pred)

    return pick_winner(results)


def choose_predictions(dnames, model_name_or_path=None, copy_md=False, devin_only=False):
    """
    Select best predictions from multiple directories of results.

    Args:
        dnames (list): List of prediction directory paths
        model_name_or_path (str, optional): Model identifier to add to predictions
        copy_md (bool): If True, copy associated markdown files
        devin_only (bool): If True, only process Devin benchmark instances

    Returns:
        dict: Best predictions for each instance, keyed by instance_id

    For each instance, selects the best prediction across all directories
    using pick_winner() criteria. Optionally copies associated markdown files
    and adds model identifier to predictions.
    """
    all_preds = [load_predictions([dname], devin_only=devin_only) for dname in dnames]
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
            assert md_fname.exists(), md_fname
            new_md_fname = pred_dname / model_name_or_path / (inst + ".md")
            shutil.copyfile(md_fname, new_md_fname)

    for inst in chosen:
        pred = dict(chosen[inst])
        pred["model_name_or_path"] = model_name_or_path
        chosen[inst] = pred

    dump(len(chosen))
    return chosen
