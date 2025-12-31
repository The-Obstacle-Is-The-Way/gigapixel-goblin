#!/usr/bin/env python3
"""Rescore all benchmark results using current extraction code.

This script re-extracts labels from saved predictions and recalculates metrics.
It preserves the original predictions but updates predicted_label and metrics.

Scoring policy:
- The primary `metrics` block is computed on "scored items only": items with
  `error != None` are excluded because there is no saved prediction text to
  re-extract from.
- Extraction failures (where we have prediction text but cannot extract a label)
  are included and count as incorrect (matching `BenchmarkRunner` behavior).
- A companion paper-faithful metric block is also computed, where errors and
  extraction failures count as incorrect (matching `BenchmarkRunner` behavior).
"""

from __future__ import annotations

import ast
import csv
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from giant.data.schemas import BENCHMARK_TASKS
from giant.eval.answer_extraction import extract_label
from giant.eval.metrics import accuracy, balanced_accuracy, bootstrap_metric

_MISSING_LABEL_SENTINEL = -1  # Must not overlap any truth label
_DEFAULT_CSV_PATH = (
    Path(__file__).parent.parent / "data" / "multipathqa" / "MultiPathQA.csv"
)


def _parse_options(options_str: str) -> list[str]:
    """Parse MultiPathQA `options` field (JSON, Python literal, or pipe-delimited)."""
    text = options_str.strip()
    if not text:
        return []

    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError) as e:
            if "|" in text:
                parsed = [part.strip() for part in text.split("|")]
            else:
                raise ValueError(f"Unparseable options field: {options_str!r}") from e

    if isinstance(parsed, tuple):
        parsed = list(parsed)
    if not isinstance(parsed, list):
        raise ValueError(
            f"Options must be a list, got {type(parsed).__name__}: {options_str!r}"
        )

    cleaned = [str(opt).strip() for opt in parsed]
    return [opt for opt in cleaned if opt]


def _load_options_by_item_id(
    *, csv_path: Path, benchmark_name: str
) -> dict[str, list[str] | None]:
    """Return a mapping of MultiPathQA benchmark_id -> parsed options list."""
    if not csv_path.exists():
        return {}

    options_by_item_id: dict[str, list[str] | None] = {}
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("benchmark_name") != benchmark_name:
                continue

            is_valid = (row.get("is_valid") or "True").strip().lower()
            if is_valid != "true":
                continue

            benchmark_id = (
                row.get("benchmark_id") or row.get("id") or row.get("image_path")
            )
            if not benchmark_id:
                continue

            options_str = (row.get("options") or "").strip()
            options = _parse_options(options_str) if options_str else []
            options_by_item_id[str(benchmark_id)] = options or None

    return options_by_item_id


def _compute_metric_bundle(
    *,
    predictions: list[int],
    truths: list[int],
    metric_fn: Callable[[list[int], list[int]], float],
    metric_type: str,
) -> dict[str, Any]:
    point = metric_fn(predictions, truths)
    boot = bootstrap_metric(predictions, truths, metric_fn)
    return {
        "metric_type": metric_type,
        "point_estimate": point,
        "bootstrap_mean": boot.mean,
        "bootstrap_std": boot.std,
        "bootstrap_ci_lower": boot.ci_lower,
        "bootstrap_ci_upper": boot.ci_upper,
        "n_replicates": boot.n_replicates,
        "format_string": f"{boot.mean:.1%} ± {boot.std:.1%}",
    }


def _get_metric_fn(
    benchmark_name: str,
) -> tuple[str, Callable[[list[int], list[int]], float]]:
    task_info = BENCHMARK_TASKS.get(benchmark_name.lower())
    if task_info is None:
        raise ValueError(f"Unknown benchmark_name: {benchmark_name!r}")

    metric_type = str(task_info["metric"])
    metric_fn = balanced_accuracy if metric_type == "balanced_accuracy" else accuracy
    return metric_type, metric_fn


def _rescore_items(
    *,
    results: list[dict[str, Any]],
    benchmark_name: str,
    options_by_item_id: dict[str, list[str] | None],
) -> tuple[int, int, int, int]:
    changed_count = 0
    extraction_failures = 0
    errors = 0
    empty_predictions = 0

    for item in results:
        if item.get("error"):
            errors += 1
            continue

        prediction = item.get("prediction") or ""
        if not prediction.strip():
            empty_predictions += 1
            continue

        item_id = str(item.get("item_id") or "")
        options = options_by_item_id.get(item_id)

        extracted = extract_label(
            prediction,
            benchmark_name=benchmark_name,
            options=options,
        )

        new_label = extracted.label
        if new_label is None:
            extraction_failures += 1

        old_label = item.get("predicted_label")
        if old_label != new_label:
            changed_count += 1
            item["predicted_label"] = new_label

        truth = item.get("truth_label")
        item["correct"] = new_label == truth if new_label is not None else False

    return changed_count, extraction_failures, errors, empty_predictions


def _collect_scored_items(results: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    predictions: list[int] = []
    truths: list[int] = []
    for item in results:
        if item.get("error"):
            continue
        prediction = item.get("prediction") or ""
        if not prediction.strip():
            continue
        label = item.get("predicted_label")
        predictions.append(label if label is not None else _MISSING_LABEL_SENTINEL)
        truths.append(item["truth_label"])
    return predictions, truths


def _collect_paper_faithful_items(
    results: list[dict[str, Any]],
) -> tuple[list[int], list[int]]:
    predictions: list[int] = []
    truths: list[int] = []
    for item in results:
        truths.append(item["truth_label"])
        if item.get("error") or item.get("predicted_label") is None:
            predictions.append(_MISSING_LABEL_SENTINEL)
        else:
            predictions.append(item["predicted_label"])
    return predictions, truths


@dataclass(frozen=True)
class RescoreCounts:
    n_total: int
    n_scored: int
    n_errors_excluded: int
    n_empty_predictions_excluded: int
    n_extraction_failures: int


def _build_metrics(
    *,
    scored_only_metrics: dict[str, Any],
    paper_faithful_metrics: dict[str, Any],
    counts: RescoreCounts,
) -> dict[str, Any]:
    return {
        **scored_only_metrics,
        "scoring_policy": "scored_items_only",
        "n_total": counts.n_total,
        "n_scored": counts.n_scored,
        "n_errors_excluded": counts.n_errors_excluded,
        "n_empty_predictions_excluded": counts.n_empty_predictions_excluded,
        "n_extraction_failures": counts.n_extraction_failures,
        "paper_faithful_point_estimate": paper_faithful_metrics["point_estimate"],
        "paper_faithful_bootstrap_mean": paper_faithful_metrics["bootstrap_mean"],
        "paper_faithful_bootstrap_std": paper_faithful_metrics["bootstrap_std"],
        "paper_faithful_bootstrap_ci_lower": paper_faithful_metrics[
            "bootstrap_ci_lower"
        ],
        "paper_faithful_bootstrap_ci_upper": paper_faithful_metrics[
            "bootstrap_ci_upper"
        ],
        "paper_faithful_format_string": paper_faithful_metrics["format_string"],
        "rescored_at": datetime.now(UTC).isoformat(),
        "rescored_with": "scripts/rescore_all.py",
    }


def rescore_file(*, file_path: Path, csv_path: Path) -> dict[str, Any]:
    """Rescore a single results file."""
    data = json.loads(file_path.read_text(encoding="utf-8"))

    benchmark_name = data["benchmark_name"]
    results = data["results"]

    metric_type, metric_fn = _get_metric_fn(benchmark_name)

    options_by_item_id = _load_options_by_item_id(
        csv_path=csv_path, benchmark_name=benchmark_name
    )

    changed_count, extraction_failures, errors, empty_predictions = _rescore_items(
        results=results,
        benchmark_name=benchmark_name,
        options_by_item_id=options_by_item_id,
    )

    predictions, truths = _collect_scored_items(results)

    if not predictions:
        raise ValueError(f"No scored items found in {file_path}")

    scored_only_metrics = _compute_metric_bundle(
        predictions=predictions,
        truths=truths,
        metric_fn=metric_fn,
        metric_type=metric_type,
    )

    paper_preds, paper_truths = _collect_paper_faithful_items(results)

    paper_faithful_metrics = _compute_metric_bundle(
        predictions=paper_preds,
        truths=paper_truths,
        metric_fn=metric_fn,
        metric_type=metric_type,
    )

    counts = RescoreCounts(
        n_total=len(results),
        n_scored=len(predictions),
        n_errors_excluded=errors,
        n_empty_predictions_excluded=empty_predictions,
        n_extraction_failures=extraction_failures,
    )
    data["metrics"] = _build_metrics(
        scored_only_metrics=scored_only_metrics,
        paper_faithful_metrics=paper_faithful_metrics,
        counts=counts,
    )

    return {
        "file": file_path.name,
        "benchmark": benchmark_name,
        "total": len(results),
        "changed": changed_count,
        "errors": errors,
        "empty_predictions": empty_predictions,
        "extraction_failures": extraction_failures,
        "new_accuracy": data["metrics"]["format_string"],
        "new_accuracy_paper_faithful": data["metrics"]["paper_faithful_format_string"],
        "data": data,
    }


def _ensure_backup(*, file_path: Path) -> None:
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    if backup_path.exists():
        return
    backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> None:
    results_dir = Path(__file__).parent.parent / "results"
    csv_path = _DEFAULT_CSV_PATH

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

        result = rescore_file(file_path=file_path, csv_path=csv_path)

        print(f"    Benchmark: {result['benchmark']}")
        print(f"    Total items: {result['total']}")
        print(f"    Labels changed: {result['changed']}")
        print(f"    API errors: {result['errors']}")
        print(f"    Empty predictions: {result['empty_predictions']}")
        print(f"    Extraction failures: {result['extraction_failures']}")
        print(f"    New accuracy: {result['new_accuracy']}")
        print(f"    Paper-faithful accuracy: {result['new_accuracy_paper_faithful']}")

        # Save back
        _ensure_backup(file_path=file_path)
        file_path.write_text(
            json.dumps(result["data"], indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"    Saved: {file_path}")

    print("\n" + "=" * 60)
    print("DONE - All files rescored and saved")
    print("=" * 60)


if __name__ == "__main__":
    main()
