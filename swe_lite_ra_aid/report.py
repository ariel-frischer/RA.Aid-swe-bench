#!/usr/bin/env python

"""
Evaluation script for RA-AID predictions on SWE-bench tasks.

Usage:
    # Run basic evaluation on predictions:
    poetry run python -m swe_lite_ra_aid.report predictions/ra_aid_predictions

    # Run evaluation with custom run ID:
    poetry run python -m swe_lite_ra_aid.report predictions/ra_aid_predictions --run-id custom_eval_run

    # Run post-evaluation analysis (WIP/Legacy):
    poetry run python -m swe_lite_ra_aid.report predictions/ra_aid_predictions --post-eval

This script:
1. Loads predictions from the specified directory
2. Filters out already evaluated predictions
3. Runs evaluation on non-evaluated predictions
4. Updates prediction files with evaluation results
5. Generates summary statistics
6. Marks prediction files with evaluated=True and resolved status after evaluating them

The post-evaluation methods starting with: `run_detailed_analysis` is borked and not yet supported legacy code.
"""

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset
from swebench.harness.constants import SWEbenchInstance
from swebench.harness.grading import (
    get_eval_report,
)
from swebench.harness.test_spec import get_test_specs_from_dataset

from .dump import dump
from .utils import LITE_DATASET, DATASET_SPLIT, RA_AID_MODEL
from .utils import (
    choose_predictions,
    load_predictions,
    old,
)

using_dataset = "lite"
NUM_EVAL_PROCS = 5
DEFAULT_EVAL_RUN_ID = "ra_aid_eval"

def print_evaluation_summary(report_file):
    """Print summary statistics from evaluation report file."""
    logger.info(f"report_file={report_file}")

    if report_file and Path(report_file).exists():
        report_data = json.loads(Path(report_file).read_text())
        summary_fields = [
            "total_instances",
            "submitted_instances", 
            "completed_instances",
            "resolved_instances",
            "unresolved_instances", 
            "empty_patch_instances",
            "error_instances",
            "unstopped_instances"
        ]
        
        logger.info("\nEvaluation Summary:")
        for field in summary_fields:
            if field in report_data:
                logger.info(f"{field}: {report_data[field]}")


def run_evals(_log_dir, predictions_jsonl, run_id=DEFAULT_EVAL_RUN_ID):
    from swebench.harness.run_evaluation import main as run_evaluation

    # Run evaluation using the swebench package directly
    report_file = run_evaluation(
        dataset_name=LITE_DATASET,
        split="test",
        instance_ids=None,
        predictions_path=predictions_jsonl,
        max_workers=NUM_EVAL_PROCS,
        force_rebuild=False,
        cache_level="env",
        clean=False,
        open_file_limit=4096,
        run_id=run_id,
        timeout=1800,
        modal=False,
    )

    print_evaluation_summary(report_file)


def create_swe_instances(dataset):
    """Create SWEbenchInstance objects from dataset items."""
    swe_instances = []
    for item in dataset:
        swe_instances.append(SWEbenchInstance(
            repo=item['repo'],
            instance_id=item['instance_id'],
            base_commit=item['base_commit'],
            patch=item['patch'],
            test_patch=item['test_patch'],
            problem_statement=item['problem_statement'],
            hints_text=item.get('hints_text', ''),
            created_at=item['created_at'],
            version=item.get('version', '1.0'),
            FAIL_TO_PASS=item['FAIL_TO_PASS'],
            PASS_TO_PASS=item['PASS_TO_PASS'],
            environment_setup_commit=item['environment_setup_commit']
        ))
    return swe_instances


def create_test_specs(swe_instances):
    """Create test specifications from SWE instances."""
    test_specs = get_test_specs_from_dataset(swe_instances)
    test_spec_dict = {spec.instance_id: spec for spec in test_specs}
    logger.info(f"Created test specs with {len(test_spec_dict)} entries")
    return test_spec_dict


def get_instance_log_path(instance_id, run_id=DEFAULT_EVAL_RUN_ID):
    """Construct the log path for a specific instance."""
    return Path("logs") / f"run_evaluation/{run_id}/{RA_AID_MODEL}" / f"{instance_id.replace('/', '__')}/run_instance.log"


def process_instance_status(instance_id, eval_result, report_stats):
    """Process evaluation result for a single instance and update report statistics."""
    try:
        # Handle case where eval_result might be a string or other non-dict
        if isinstance(eval_result, str):
            logger.warning(f"eval_result for {instance_id} is a string: {eval_result}")
            return

        if not isinstance(eval_result, dict):
            logger.warning(f"eval_result for {instance_id} is not a dictionary, got {type(eval_result)}")
            return

        # Check FAIL_TO_PASS tests directly instead of using get_resolution_status
        fail_to_pass = eval_result.get("tests_status", {}).get("FAIL_TO_PASS", {})
        if isinstance(fail_to_pass, dict) and fail_to_pass.get("success", False):
            report_stats["resolved"].add(instance_id)

        if eval_result.get("model_patch"):
            report_stats["generated"].add(instance_id)
        else:
            report_stats["no_generation"].add(instance_id)

        if eval_result.get("applied", False):
            report_stats["applied"].add(instance_id)

        if eval_result.get("logs"):
            report_stats["with_logs"].add(instance_id)

        if not eval_result.get("applied", False):
            report_stats["no_apply"].add(instance_id)

    except Exception as e:
        logger.error(f"Error processing instance {instance_id}: {e}")


def output_report_stats(report_stats):
    """Output detailed statistics about the evaluation results."""
    logger.info("\nReport Statistics:")
    for key, value in report_stats.items():
        logger.info(f"{key}: {len(value)}")

    dump(sorted(report_stats["resolved"]))

    generated_minus_applied = report_stats["generated"] - report_stats["applied"]
    dump(len(generated_minus_applied))
    generated_minus_applied = " ".join(iid + "*" for iid in sorted(generated_minus_applied))
    dump(generated_minus_applied)

    with_logs_minus_applied = report_stats["with_logs"] - report_stats["applied"]
    dump(len(with_logs_minus_applied))
    dump(with_logs_minus_applied)

    dump(len(report_stats["no_apply"]))
    no_apply = " ".join(iid + "*" for iid in sorted(report_stats["no_apply"]))
    dump(no_apply)


def process_single_prediction(prediction, test_spec):
    """Process a single prediction and return its evaluation report."""
    instance_id = prediction['instance_id']
    
    if instance_id not in test_spec:
        return None, None
        
    print(f"\nProcessing instance: {instance_id}")
    instance_log_path = get_instance_log_path(instance_id)
    
    if not instance_log_path.exists():
        print(f"Warning: Log file not found at {instance_log_path}")
        return instance_id, {
            "patch_exists": False,
            "patch_successfully_applied": False,
            "tests_status": None
        }
    
    single_report = get_eval_report(
        test_spec=test_spec[instance_id],
        prediction=prediction,
        log_path=str(instance_log_path),
        include_tests_status=True,
    )
    
    return instance_id, single_report.get(instance_id, {}) if single_report else None


def get_report(dataset, _log_dir, predictions_jsonl, _model_name_or_path):
    """Generate evaluation report for predictions."""
    try:
        # Create SWE instances and test specs
        swe_instances = create_swe_instances(dataset)
        test_spec = create_test_specs(swe_instances)
        
        # Process predictions
        report = {}
        with open(predictions_jsonl, 'r') as f:
            for line in f:
                prediction = json.loads(line)
                instance_id, result = process_single_prediction(prediction, test_spec)
                if instance_id and result:
                    report[instance_id] = result
                        

        report_stats = {
            "resolved": set(),
            "generated": set(),
            "applied": set(),
            "with_logs": set(),
            "no_apply": set(),
            "no_generation": set(),
        }

        # Process each instance's status
        for instance_id, eval_result in report.items():
            process_instance_status(instance_id, eval_result, report_stats)

        # Output debug statistics
        output_report_stats(report_stats)

        return report_stats

    except Exception as e:
        import traceback
        print(f"Error generating report: {e}")
        traceback.print_exc()
        return dict()


def update_pred_json(predictions, report):
    if not report:
        return predictions

    for instance_id, pred in predictions.items():
        # Update resolved status
        was_resolved = instance_id in report.get("resolved", set())
        needs_update = (
            "resolved" not in pred 
            or pred["resolved"] != was_resolved 
            or not pred.get("evaluated", False)
        )
        
        if needs_update:
            pred["resolved"] = was_resolved
            pred["evaluated"] = True
            save = dict(pred)
            del save["json_fname"]
            Path(pred["json_fname"]).write_text(json.dumps(save, indent=4))

    return predictions


def preds_to_jsonl(dname, predictions):
    dname = Path(dname)
    predictions_jsonl = str(dname / "all_preds.jsonl")
    dump(predictions_jsonl)

    # Use consistent model name if not present in predictions
    model_name_or_path = RA_AID_MODEL

    with open(predictions_jsonl, "w") as fh:
        for _, pred in predictions.items():
            minimal_pred = {
                "instance_id": pred["instance_id"],
                "model_name_or_path": model_name_or_path,
                "model_patch": pred["model_patch"],
                # "model_patch": remove_patches_to_tests(pred["model_patch"])
                "ra_aid_model": pred.get(
                    "ra_aid_model", "openrouter/deepseek/deepseek-chat"
                ),
                "ra_aid_editor": pred.get(
                    "ra_aid_editor", "anthropic/claude-3-5-sonnet-20241022"
                ),
                "timestamp": pred.get("timestamp", ""),
            }
            fh.write(json.dumps(minimal_pred) + "\n")
    return predictions_jsonl


def run_evals_on_dname(dname, dataset, run_id=DEFAULT_EVAL_RUN_ID):
    """Run evaluations on predictions in directory.
    Note: get_report functionality is currently WIP/broken, using default empty report."""
    dname = Path(dname)

    predictions = load_predictions([dname])
    predictions_jsonl = None

    log_dir = Path("logs") / dname.name
    log_dir.mkdir(exist_ok=True, parents=True)
    dump(log_dir)

    # Filter out already evaluated predictions
    non_evaluated_predictions = {
        k: v for k, v in predictions.items() 
        if not v.get("evaluated", False)
    }

    if non_evaluated_predictions:
        # Generate JSONL only for predictions that need evaluation
        predictions_jsonl = preds_to_jsonl(dname, non_evaluated_predictions)
        
        run_evals(str(log_dir), predictions_jsonl, run_id)

        model_name_or_path = list(predictions.values())[0]["model_name_or_path"]
        print(f"model_name_or_path={model_name_or_path}")
        
        # get_report is currently WIP/broken
        # report = get_report(
        #     dataset,
        #     log_dir,
        #     predictions_jsonl,
        #     model_name_or_path,
        # )
        
        # Use empty default report for now
        report = {"resolved": set()}
        predictions = update_pred_json(predictions, report)
    else:
        print("All predictions already evaluated")
        report_file = Path(f"{RA_AID_MODEL}.{run_id}.json")
        print(f"Current report_file path: {report_file}")
        print_evaluation_summary(report_file)

    return predictions_jsonl, log_dir


def combine_jsonl_logs(predictions, model_name_or_path):
    logs = Path("logs")
    log_dir = logs / model_name_or_path
    old(log_dir)

    log_dir.mkdir(exist_ok=True)
    dump(log_dir)

    preds_dir = Path("predictions") / model_name_or_path

    predictions_jsonl = preds_to_jsonl(preds_dir, predictions)
    for inst, pred in predictions.items():
        from_fname = logs / pred["dname"]
        # dump(from_fname, inst)
        from_fname = list(from_fname.glob(f"{inst}.*.log"))
        assert len(from_fname) <= 1, from_fname
        if not len(from_fname):
            print("Missing", pred["dname"], inst)
            continue
        from_fname = from_fname[0]
        to_fname = log_dir / f"{inst}.{model_name_or_path}.eval.log"
        shutil.copyfile(from_fname, to_fname)

    return predictions_jsonl, log_dir


def evaluate_predictions(dnames, dataset, run_id=DEFAULT_EVAL_RUN_ID):
    """Process all prediction directories and run evaluations."""
    for dname in dnames:
        dump(dname)
        run_evals_on_dname(dname, dataset, run_id)


def setup_output_directory(model_name_or_path):
    """Setup the output directory for predictions."""
    preds_dir = Path("predictions") / model_name_or_path
    old(preds_dir)
    preds_dir.mkdir(exist_ok=True)
    return preds_dir


def process_single_eval_result(instance_id, eval_result, report_stats):
    """Process a single evaluation result and update report statistics."""
    if not isinstance(eval_result, dict):
        print(f"Warning: eval_result for {instance_id} is not a dictionary")
        return

    # Track basic stats
    if eval_result.get("patch_exists", False):
        report_stats["generated"].add(instance_id)
    else:
        report_stats["no_generation"].add(instance_id)

    if eval_result.get("patch_successfully_applied", False):
        report_stats["applied"].add(instance_id)
    else:
        report_stats["no_apply"].add(instance_id)

    if eval_result.get("tests_status"):
        report_stats["with_logs"].add(instance_id)

    # Check if any FAIL_TO_PASS tests succeeded
    fail_to_pass = eval_result.get("tests_status", {}).get("FAIL_TO_PASS", {})
    if isinstance(fail_to_pass, dict) and fail_to_pass.get("success"):
        report_stats["resolved"].add(instance_id)


def process_report_statistics(report, counts):
    """Process and display basic report statistics."""
    report_stats = {
        "resolved": set(),
        "generated": set(),
        "applied": set(),
        "with_logs": set(),
        "no_apply": set(),
        "no_generation": set()
    }

    if not isinstance(report, dict):
        print(f"Warning: report is not a dictionary, got {type(report)}")
        return report_stats, 0, 0

    for instance_id, eval_result in report.items():
        try:
            process_single_eval_result(instance_id, eval_result, report_stats)
        except Exception as e:
            print(f"Error processing instance {instance_id}: {e}")
            continue

    # Update counts
    for key, value in report_stats.items():
        counts[key] = len(value)

    print("\nReport Statistics:")
    for key, value in counts.items():
        print(f"{key}: {value}")

    total = len(report)
    missing_logs = total - counts["with_logs"] if total > 0 else 0

    if total:
        percent = counts["resolved"] * 100 / total
        print(f"\nResolved percentage: {percent:.1f}%")

    return report_stats, total, missing_logs


def analyze_missing_runs(total, missing_logs, counts):
    """Analyze and display statistics about missing runs."""
    need_to_be_run = missing_logs - counts["no_generation"]
    if need_to_be_run:
        dump(need_to_be_run)
        should_count = total - need_to_be_run
        dump(should_count)
        percent_of_should = counts["resolved"] * 100 / should_count
        print(f"{percent_of_should=:.1f}")
    return need_to_be_run


def calculate_costs(predictions, dataset):
    """Calculate and display cost statistics."""
    costs = [
        data.get("cost")
        for data in predictions.values()
        if data.get("cost") is not None and data.get("cost") > 0
    ]

    if costs:
        recent = [f"{c:.2f}" for c in costs[-5:]]
        print("recent costs:", ", ".join(recent))
        avg_cost = sum(costs) / len(costs)
        print(f"avg_cost: ${avg_cost:.2f}/instance")
        spent = sum(costs)
        print(f"spent: ${spent:.2f}")

        num_instances = len(list(dataset))

        expected_cost = num_instances * avg_cost
        print(f"expected_cost: ${expected_cost:.2f}")
        print()


def analyze_gold_files(predictions):
    """Analyze statistics related to gold files."""
    stats = {
        "total_plausible": 0,
        "resolved_plausible": 0,
        "total_with_added": 0,
        "total_with_gold_attr": 0,
        "total_added_gold": 0,
        "gold_resolved": 0,
        "added_timeline": "",
        "repomap_timeline": "",
        "timeline": "",
    }

    for _, data in predictions.items():
        gold_files = set(data.get("gold_files", []))
        added_files = set(data.get("added_files", []))

        resolved = data.get("resolved")
        added_gold = (added_files.intersection(gold_files) == gold_files) and gold_files

        plausible = data["model_patch"] and data["edited_files"]
        if plausible:
            stats["total_plausible"] += 1
            if resolved:
                stats["resolved_plausible"] += 1

        if added_files:
            stats["total_with_added"] += 1
            stats["added_timeline"] += str(len(added_files))
        else:
            stats["added_timeline"] += "_"

        if gold_files:
            stats["total_with_gold_attr"] += 1
        if added_gold:
            stats["total_added_gold"] += 1

        stats["timeline"] += get_timeline_marker(gold_files, resolved, added_gold)
        stats["repomap_timeline"] += (
            "M"
            if data.get("initial_map_has_gold_file") or data.get("map_has_gold_file")
            else "_"
        )

        if added_gold and resolved:
            stats["gold_resolved"] += 1

    return stats


def get_timeline_marker(gold_files, resolved, added_gold):
    """Get the appropriate timeline marker based on conditions."""
    if not gold_files and not resolved:
        return "."
    elif added_gold and resolved:
        return "R"
    elif added_gold and not resolved:
        return "g"
    elif not added_gold and not resolved:
        return "_"
    elif not added_gold and resolved:
        return "!"
    return "_"


def display_gold_stats(stats, total):
    """Display statistics related to gold files."""
    pct_maps_with_gold_file = (
        len(stats["repomap_timeline"].replace("_", ""))
        / len(stats["repomap_timeline"])
        * 100
        if stats.get("repomap_timeline")
        else 0
    )
    dump(pct_maps_with_gold_file)

    dump(stats["total_with_gold_attr"])
    dump(stats["total_added_gold"])

    if stats["total_with_gold_attr"]:
        pct_added = stats["total_added_gold"] / stats["total_with_gold_attr"] * 100
        print(f"pct_added_gold: {pct_added:.1f}%")

    if stats["total_added_gold"]:
        pct_added_gold_resolved = (
            stats["gold_resolved"] / stats["total_added_gold"] * 100
        )
        print(f"pct_added_gold_resolved: {pct_added_gold_resolved:.1f}%")
        print()

    dump(stats["total_with_added"])
    if total > 0:  # Add check for zero
        pct_with_added = stats["total_with_added"] / total * 100
        dump(pct_with_added)
    print()

    dump(stats["total_plausible"])
    dump(stats["resolved_plausible"])
    if stats["total_plausible"]:
        pct_resolved_plausible = (
            100 * stats["resolved_plausible"] / stats["total_plausible"]
        )
        dump(pct_resolved_plausible)

    if total > 0:
        pct_plausible = stats["total_plausible"] / total * 100
        dump(pct_plausible)
    else:
        print("No total instances found - cannot calculate percentage plausible")


def run_detailed_analysis(dnames: list, dataset, model_name_or_path: str = "ra_aid_selected_predictions"):
    """
    Run detailed post-evaluation analysis on predictions.
    
    Args:
        dnames: List of prediction directory paths
        dataset: Loaded SWE-bench dataset
        model_name_or_path: Name of the model/prediction set
    """
    print("Running run_detailed_analysis")
    _preds_dir = setup_output_directory(model_name_or_path)

    predictions = choose_predictions(dnames, model_name_or_path, copy_md=True)
    if not predictions:
        print("No predictions")
        return
    dump(len(predictions))

    predictions_jsonl, log_dir = combine_jsonl_logs(predictions, model_name_or_path)
    report = get_report(dataset, log_dir, predictions_jsonl, model_name_or_path)

    results_json = Path("predictions") / model_name_or_path / "results.json"
    results_json.write_text(json.dumps(report, indent=4))

    counts = defaultdict(int, [(k, len(v)) for k, v in report.items()])
    print(f"counts={counts}")
    total, missing_logs = process_report_statistics(report, counts)

    _need_to_be_run = analyze_missing_runs(total, missing_logs, counts)

    calculate_costs(predictions, dataset)

    stats = analyze_gold_files(predictions)
    display_gold_stats(stats, total)


def main():
    """Main function to process and analyze predictions."""
    parser = argparse.ArgumentParser(description="Evaluate RA-AID predictions")
    parser.add_argument("directories", nargs="+", help="Prediction directories to evaluate")
    parser.add_argument("--post-eval", action="store_true", default=False,
                       help="Run detailed post-evaluation analysis. WIP / Not yet supported legacy code")
    parser.add_argument("--run-id", default=DEFAULT_EVAL_RUN_ID,
                       help="Run ID for evaluation, specifies the eval json filename (default: ra_aid_eval)")
    args = parser.parse_args()

    dataset = load_dataset(LITE_DATASET, split=DATASET_SPLIT)

    evaluate_predictions(args.directories, dataset, args.run_id)

    if args.post_eval:
        run_detailed_analysis(args.directories, dataset)


if __name__ == "__main__":
    status = main()
    sys.exit(status)
