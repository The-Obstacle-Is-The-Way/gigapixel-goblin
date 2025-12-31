#!/usr/bin/env python3
"""Rescore all benchmark results using current extraction code.

This script re-extracts labels from saved predictions and recalculates metrics.
It preserves the original predictions but updates predicted_label and metrics.
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from giant.eval.answer_extraction import extract_label
from giant.eval.metrics import balanced_accuracy, bootstrap_metric


def rescore_file(file_path: Path) -> dict:
    """Rescore a single results file."""
    with open(file_path) as f:
        data = json.load(f)

    benchmark_name = data["benchmark_name"]
    results = data["results"]

    # Track changes
    changed_count = 0
    extraction_failures = 0
    errors = 0

    for item in results:
        # Skip if there was an API error (no prediction to extract from)
        if item.get("error"):
            errors += 1
            continue

        prediction = item.get("prediction", "")
        if not prediction:
            extraction_failures += 1
            continue

        # Get options if available (for non-PANDA benchmarks)
        options = item.get("options")

        # Re-extract label using current code
        extracted = extract_label(
            prediction, benchmark_name=benchmark_name, options=options
        )

        old_label = item.get("predicted_label")
        new_label = extracted.label

        if new_label is None:
            extraction_failures += 1

        if old_label != new_label:
            changed_count += 1
            item["predicted_label"] = new_label

        # Recalculate correctness
        truth = item.get("truth_label")
        item["correct"] = new_label == truth if new_label is not None else False

    # Collect labels for metrics
    predictions = []
    truths = []
    for item in results:
        if item.get("error") or item.get("predicted_label") is None:
            continue
        predictions.append(item["predicted_label"])
        truths.append(item["truth_label"])

    # Recalculate metrics
    if predictions and truths:
        point = balanced_accuracy(predictions, truths)
        boot = bootstrap_metric(predictions, truths, balanced_accuracy)
        format_str = f"{boot.mean * 100:.1f}% ± {boot.std * 100:.1f}%"

        data["metrics"] = {
            "metric_type": "balanced_accuracy",
            "point_estimate": point,
            "bootstrap_mean": boot.mean,
            "bootstrap_std": boot.std,
            "bootstrap_ci_lower": boot.ci_lower,
            "bootstrap_ci_upper": boot.ci_upper,
            "n_replicates": boot.n_replicates,
            "n_total": len(results),
            "n_errors": errors,
            "n_extraction_failures": extraction_failures,
            "format_string": format_str,
        }

    return {
        "file": file_path.name,
        "benchmark": benchmark_name,
        "total": len(results),
        "changed": changed_count,
        "errors": errors,
        "extraction_failures": extraction_failures,
        "old_metrics": None,  # Could track but not needed
        "new_accuracy": data["metrics"]["format_string"],
        "data": data,
    }


def main():
    results_dir = Path(__file__).parent.parent / "results"

    files = [
        "panda_giant_openai_gpt-5.2_results.json",
        "gtex_giant_openai_gpt-5.2_results.json",
        "tcga_giant_openai_gpt-5.2_results.json",
    ]

    print("=" * 60)
    print("RESCORING ALL BENCHMARK RESULTS")
    print("=" * 60)

    for filename in files:
        file_path = results_dir / filename
        if not file_path.exists():
            print(f"\nSkipping {filename} (not found)")
            continue

        print(f"\n>>> Processing: {filename}")

        result = rescore_file(file_path)

        print(f"    Benchmark: {result['benchmark']}")
        print(f"    Total items: {result['total']}")
        print(f"    Labels changed: {result['changed']}")
        print(f"    API errors: {result['errors']}")
        print(f"    Extraction failures: {result['extraction_failures']}")
        print(f"    New accuracy: {result['new_accuracy']}")

        # Save back
        with open(file_path, "w") as f:
            json.dump(result["data"], f, indent=2)
        print(f"    Saved: {file_path}")

    print("\n" + "=" * 60)
    print("DONE - All files rescored and saved")
    print("=" * 60)


if __name__ == "__main__":
    main()
