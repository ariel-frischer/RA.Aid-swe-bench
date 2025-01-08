#!/usr/bin/env python

import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset
from swebench.harness.grading import (
    get_eval_report,
    get_resolution_status,
    ResolvedStatus,
)

from .dump import dump  # noqa: F401

from .utils import (
    choose_predictions,
    get_devin_instance_ids,
    load_predictions,
    old,
)

using_dataset = "lite"

NUM_EVAL_PROCS = 5


def run_evals(_log_dir, predictions_jsonl):
    from swebench.harness.run_evaluation import main as run_evaluation

    # Run evaluation using the swebench package directly
    run_evaluation(
        dataset_name="princeton-nlp/SWE-bench_Lite",
        split="test",
        instance_ids=None,
        predictions_path=predictions_jsonl,
        max_workers=NUM_EVAL_PROCS,
        force_rebuild=False,
        cache_level="env",
        clean=False,
        open_file_limit=4096,
        run_id="ra_aid_eval",
        timeout=1800,
    )


def get_report(dataset, log_dir, predictions_jsonl, _model_name_or_path):
    try:
        test_spec = list(dataset)
        print(f"test_spec={test_spec}")

        report = get_eval_report(
            test_spec=test_spec,
            prediction=predictions_jsonl,
            log_path=str(log_dir),
            include_tests_status=True,
        )
        print(f"report={report}")

        # Initialize report_stats with empty sets
        report_stats = {
            "resolved": set(),
            "generated": set(),
            "applied": set(),
            "with_logs": set(),
            "no_apply": set(),
            "no_generation": set(),
        }

        print(f"Raw report: {report}")  # Debug print

        if not isinstance(report, dict):
            print(f"Warning: report is not a dictionary, got {type(report)}")
            return report_stats

        # Process each instance's status
        for instance_id, eval_result in report.items():
            try:
                # Handle case where eval_result might be a string or other non-dict
                if isinstance(eval_result, str):
                    print(
                        f"Warning: eval_result for {instance_id} is a string: {eval_result}"
                    )
                    continue

                if not isinstance(eval_result, dict):
                    print(
                        f"Warning: eval_result for {instance_id} is not a dictionary, got {type(eval_result)}"
                    )
                    continue

                # Safely get resolution status with error handling
                try:
                    resolution_status = get_resolution_status(eval_result)
                except Exception as e:
                    print(f"Error getting resolution status for {instance_id}: {e}")
                    continue

                # Track instance in appropriate categories
                if resolution_status == ResolvedStatus.RESOLVED:
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
                print(f"Error processing instance {instance_id}: {e}")
                continue

        # Debug output
        print("\nReport Statistics:")
        for key, value in report_stats.items():
            print(f"{key}: {len(value)}")

        dump(sorted(report_stats["resolved"]))

        generated_minus_applied = report_stats["generated"] - report_stats["applied"]
        dump(len(generated_minus_applied))
        generated_minus_applied = " ".join(
            iid + "*" for iid in sorted(generated_minus_applied)
        )
        dump(generated_minus_applied)

        with_logs_minus_applied = report_stats["with_logs"] - report_stats["applied"]
        dump(len(with_logs_minus_applied))
        dump(with_logs_minus_applied)

        dump(len(report_stats["no_apply"]))
        no_apply = " ".join(iid + "*" for iid in sorted(report_stats["no_apply"]))
        dump(no_apply)

        return report_stats

    except Exception as e:
        print(f"Error generating report: {e}")
        return dict()


def update_pred_json(predictions, report):
    if not report:
        return predictions

    all_instances = set(report.get("generated", []))
    all_instances.update(set(report.get("no_generation", [])))

    for instance_id, pred in predictions.items():
        was_resolved = instance_id in report.get("resolved", set())
        if "resolved" in pred and pred["resolved"] == was_resolved:
            continue

        assert instance_id in all_instances, instance_id

        pred["resolved"] = was_resolved
        save = dict(pred)
        del save["json_fname"]
        Path(pred["json_fname"]).write_text(json.dumps(save, indent=4))

    return predictions


def preds_to_jsonl(dname, predictions):
    dname = Path(dname)
    predictions_jsonl = str(dname / "all_preds.jsonl")
    dump(predictions_jsonl)

    # Use consistent model name if not present in predictions
    model_name_or_path = "ra-aid-model"

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


def run_evals_on_dname(dname):
    dname = Path(dname)

    predictions = load_predictions([dname], devin_only=(using_dataset == "devin"))

    predictions_jsonl = preds_to_jsonl(dname, predictions)
    dump(predictions_jsonl)

    log_dir = Path("logs") / dname.name
    log_dir.mkdir(exist_ok=True, parents=True)
    dump(log_dir)

    any_need_evals = any("resolved" not in pred for pred in predictions.values())
    any_need_evals = True
    if any_need_evals:
        run_evals(str(log_dir), predictions_jsonl)

        model_name_or_path = list(predictions.values())[0]["model_name_or_path"]
        report = get_report(
            "princeton-nlp/SWE-bench_Lite",
            log_dir,
            predictions_jsonl,
            model_name_or_path,
        )
        predictions = update_pred_json(predictions, report)

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
        # dump(from_fname)

        to_fname = log_dir / f"{inst}.{model_name_or_path}.eval.log"
        # dump(from_fname, to_fname)
        shutil.copyfile(from_fname, to_fname)

    return predictions_jsonl, log_dir


def process_predictions_directories(dnames):
    """Process all prediction directories and run evaluations."""
    for dname in dnames:
        dump(dname)
        run_evals_on_dname(dname)


def setup_output_directory(model_name_or_path):
    """Setup the output directory for predictions."""
    preds_dir = Path("predictions") / model_name_or_path
    old(preds_dir)
    preds_dir.mkdir(exist_ok=True)
    return preds_dir


def process_report_statistics(report_stats, counts):
    """Process and display basic report statistics."""
    # Ensure we have valid input
    if not isinstance(report_stats, dict):
        print(f"Warning: report_stats is not a dictionary, got {type(report_stats)}")
        return 0, 0

    # Convert sets to counts with validation
    for key, value in report_stats.items():
        if isinstance(value, (set, list)):
            counts[key] = len(value)
        else:
            print(f"Warning: value for {key} is not a set/list, got {type(value)}")
            counts[key] = 0

    print(f"Debug - report_stats keys: {report_stats.keys()}")
    print(f"Debug - counts: {dict(counts)}")

    total = counts["generated"] + counts["no_generation"]
    missing_logs = total - counts["with_logs"]
    dump(counts)
    dump(total)
    dump(missing_logs)

    if total:
        percent = counts["resolved"] * 100 / total
        print(f"{percent= :.1f}%")
        plus_one_percent = (counts["resolved"] + 1) * 100 / (total + 1)
        print(f"{plus_one_percent= :.1f}%")
    print()
    return total, missing_logs


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

        if using_dataset == "devin":
            num_instances = len(get_devin_instance_ids())
        else:
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


def main():
    """Main function to process and analyze predictions."""
    dnames = sys.argv[1:]
    model_name_or_path = "ra_aid_selected_predictions"

    # Load dataset once
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    process_predictions_directories(dnames)
    _preds_dir = setup_output_directory(model_name_or_path)

    predictions = choose_predictions(
        dnames, model_name_or_path, copy_md=True, devin_only=(using_dataset == "devin")
    )
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


if __name__ == "__main__":
    status = main()
    sys.exit(status)
