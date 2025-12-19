"""Benchmark runner for batch evaluation (Spec-10).

Provides the BenchmarkRunner class that:
- Loads MultiPathQA benchmark items from CSV
- Resolves WSI paths under a user-provided wsi_root
- Runs the GIANT agent in batch mode with concurrency control
- Extracts and scores answers
- Saves results with full provenance
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from giant.agent.runner import AgentConfig, GIANTAgent, RunResult
from giant.data.schemas import BENCHMARK_TASKS, BenchmarkItem, BenchmarkResult
from giant.eval.answer_extraction import extract_label
from giant.eval.metrics import (
    accuracy,
    balanced_accuracy,
    bootstrap_metric,
)
from giant.eval.resumable import CheckpointManager, CheckpointState

if TYPE_CHECKING:
    from giant.llm.protocol import LLMProvider

logger = logging.getLogger(__name__)

_MISSING_LABEL_SENTINEL = -1

_SAFE_FILENAME_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


class EvaluationConfig(BaseModel):
    """Configuration for benchmark evaluation.

    Attributes:
        max_steps: Maximum navigation steps per item (default: 20 per paper).
        runs_per_item: Number of runs per item for majority voting (default: 1).
        max_concurrent: Maximum concurrent agent runs.
        save_trajectories: Whether to save full trajectories.
        checkpoint_interval: Save checkpoint every N items.
    """

    max_steps: int = Field(default=20, ge=1)
    runs_per_item: int = Field(default=1, ge=1)
    max_concurrent: int = Field(default=4, ge=1)
    save_trajectories: bool = True
    checkpoint_interval: int = Field(default=10, ge=1)


class EvaluationResults(BaseModel):
    """Full results from a benchmark evaluation.

    Attributes:
        run_id: Unique identifier for this evaluation run.
        benchmark_name: Name of the evaluated benchmark.
        model_name: Name of the LLM model used.
        config: Evaluation configuration used.
        results: List of individual item results.
        metrics: Computed metrics with bootstrap uncertainty.
        total_cost_usd: Total cost of the evaluation.
        total_tokens: Total tokens used.
        timestamp: When the evaluation was run.
    """

    run_id: str
    benchmark_name: str
    model_name: str
    config: EvaluationConfig
    results: list[BenchmarkResult]
    metrics: dict[str, Any] = Field(default_factory=dict)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    timestamp: str = ""


class BenchmarkRunner:
    """Runs GIANT agent on benchmark items with evaluation.

    Usage:
        runner = BenchmarkRunner(
            llm_provider=provider,
            wsi_root="/data/wsi",
            output_dir="/results",
        )
        results = await runner.run_benchmark(
            benchmark_name="tcga",
            csv_path="/data/MultiPathQA.csv",
        )
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        wsi_root: Path | str,
        output_dir: Path | str,
        config: EvaluationConfig | None = None,
    ) -> None:
        """Initialize the benchmark runner.

        Args:
            llm_provider: LLM provider for the GIANT agent.
            wsi_root: Root directory containing WSI files.
            output_dir: Directory to save results and trajectories.
            config: Evaluation configuration.
        """
        self.llm_provider = llm_provider
        self.wsi_root = Path(wsi_root)
        self.output_dir = Path(output_dir)
        self.config = config or EvaluationConfig()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_manager = CheckpointManager(self.output_dir / "checkpoints")

    def load_benchmark_items(
        self,
        csv_path: Path | str,
        benchmark_name: str,
    ) -> list[BenchmarkItem]:
        """Load benchmark items from MultiPathQA CSV.

        Args:
            csv_path: Path to MultiPathQA.csv.
            benchmark_name: Benchmark to filter (tcga, panda, gtex, etc.).

        Returns:
            List of BenchmarkItem for the specified benchmark.

        Raises:
            FileNotFoundError: If CSV file doesn't exist.
            ValueError: If benchmark name is invalid.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"MultiPathQA CSV not found: {csv_path}")

        if benchmark_name not in BENCHMARK_TASKS:
            raise ValueError(
                f"Unknown benchmark: {benchmark_name}. "
                f"Valid options: {list(BENCHMARK_TASKS.keys())}"
            )

        task_info = BENCHMARK_TASKS[benchmark_name]
        items = []

        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Filter by benchmark name and validity
                if row.get("benchmark_name") != benchmark_name:
                    continue
                if row.get("is_valid", "True").lower() != "true":
                    continue

                # Resolve WSI path
                image_path = row["image_path"]
                wsi_path = self._resolve_wsi_path(image_path, benchmark_name)

                # Parse options if present
                options = None
                options_str = row.get("options", "")
                if options_str:
                    try:
                        options = json.loads(options_str)
                    except json.JSONDecodeError:
                        # Try splitting by common delimiters
                        options = [o.strip() for o in options_str.split("|")]

                # Build prompt (substitute {options} if needed)
                prompt = row.get("prompt", row.get("question", ""))
                if options and "{options}" in prompt:
                    formatted_options = "\n".join(
                        f"{i}. {opt}" for i, opt in enumerate(options, start=1)
                    )
                    prompt = prompt.replace("{options}", formatted_options)

                # Parse truth label
                try:
                    truth_label = self._parse_truth_label(
                        row.get("answer", ""),
                        benchmark_name,
                        options,
                    )
                except ValueError as e:
                    row_id = row.get("id", row.get("image_path", "<unknown>"))
                    raise ValueError(
                        f"Invalid truth label for row {row_id!r}: {e}"
                    ) from e

                item = BenchmarkItem(
                    benchmark_name=benchmark_name,
                    benchmark_id=row.get("id", row.get("image_path", "")),
                    image_path=image_path,
                    prompt=prompt,
                    options=options,
                    metric_type=str(task_info["metric"]),
                    truth_label=truth_label,
                    wsi_path=str(wsi_path),
                )
                items.append(item)

        logger.info(
            "Loaded %d items for benchmark %s",
            len(items),
            benchmark_name,
        )
        return items

    def _resolve_wsi_path(self, image_path: str, benchmark_name: str) -> Path:
        """Resolve WSI path under wsi_root.

        Tries:
        1. wsi_root / image_path
        2. wsi_root / benchmark_name / image_path

        Args:
            image_path: Filename from CSV.
            benchmark_name: Benchmark name for subdirectory.

        Returns:
            Resolved path to WSI file.

        Raises:
            FileNotFoundError: If WSI file is not found.
            ValueError: If image_path attempts path traversal.
        """
        image_rel = Path(image_path)
        if image_rel.is_absolute() or image_rel.drive:
            raise ValueError(
                f"Invalid image_path {image_path!r}: absolute paths are not allowed."
            )
        if ".." in image_rel.parts:
            raise ValueError(
                f"Invalid image_path {image_path!r}: path traversal is not allowed."
            )

        # Try direct path
        direct_path = self.wsi_root / image_rel
        if direct_path.exists():
            return direct_path

        # Try benchmark subdirectory
        subdir_path = self.wsi_root / benchmark_name / image_rel
        if subdir_path.exists():
            return subdir_path

        raise FileNotFoundError(
            f"WSI not found: tried {direct_path} and {subdir_path}. "
            f"Please ensure the WSI is available under --wsi-root."
        )

    def _parse_truth_label(
        self,
        answer: str,
        benchmark_name: str,
        options: list[str] | None,
    ) -> int:
        """Parse truth label from CSV answer field.

        Conventions:
        - Integer strings: direct conversion (1-based for options).
        - String labels (GTEx): find index in options + 1.
        - PANDA: ISUP grade 0-5.

        Args:
            answer: Raw answer value from CSV.
            benchmark_name: Benchmark name for context.
            options: Options list if available.

        Returns:
            Canonicalized integer truth label.
        """
        answer = answer.strip()
        if not answer:
            raise ValueError("Empty truth label")

        # Try integer conversion first
        try:
            return int(answer)
        except ValueError:
            pass

        # GTEx: string label to index
        if options:
            for i, opt in enumerate(options, start=1):
                if opt == answer:
                    return i

            answer_lower = answer.lower()
            for i, opt in enumerate(options, start=1):
                if opt.lower() == answer_lower:
                    return i

        raise ValueError(
            f"Could not parse truth label {answer!r} for benchmark {benchmark_name!r}"
        )

    async def run_benchmark(
        self,
        benchmark_name: str,
        csv_path: Path | str,
        run_id: str | None = None,
    ) -> EvaluationResults:
        """Run evaluation on a benchmark.

        Args:
            benchmark_name: Benchmark to evaluate (tcga, panda, etc.).
            csv_path: Path to MultiPathQA.csv.
            run_id: Optional run ID (auto-generated if not provided).

        Returns:
            EvaluationResults with all results and metrics.
        """
        # Generate run ID if not provided
        if run_id is None:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            run_id = f"{benchmark_name}_{timestamp}"
        self._validate_run_id(run_id)

        # Load items
        items = self.load_benchmark_items(csv_path, benchmark_name)

        # Load or create checkpoint
        checkpoint = self._checkpoint_manager.load_or_create(
            run_id,
            benchmark_name,
            config=self.config.model_dump(),
        )

        # Filter out completed items
        pending_items = [
            item for item in items if item.benchmark_id not in checkpoint.completed_ids
        ]

        logger.info(
            "Running evaluation: %d pending, %d completed",
            len(pending_items),
            len(checkpoint.completed_ids),
        )

        # Run agent on pending items with bounded concurrency.
        # NOTE: Avoid creating one Task per item; use a fixed worker pool.
        try:
            await self._run_pending_items(pending_items, checkpoint)
        finally:
            # Always persist the latest state (even on cancellation) so we can resume.
            self._checkpoint_manager.save(checkpoint)

        # Compute metrics
        metrics = self._compute_metrics(checkpoint.results, benchmark_name)

        # Build final results
        total_cost = sum(r.cost_usd for r in checkpoint.results)
        total_tokens = sum(r.total_tokens for r in checkpoint.results)

        results = EvaluationResults(
            run_id=run_id,
            benchmark_name=benchmark_name,
            model_name=self.llm_provider.get_model_name(),
            config=self.config,
            results=checkpoint.results,
            metrics=metrics,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Save final results
        self._save_results(results)

        return results

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        run_id_path = Path(run_id)
        if (
            run_id_path.is_absolute()
            or ".." in run_id_path.parts
            or run_id_path.name != run_id
        ):
            raise ValueError(
                f"Invalid run_id {run_id!r}: must be a simple filename "
                "(no path traversal)."
            )

    @staticmethod
    def _safe_filename_component(value: str) -> str:
        """Return a filesystem-safe component for filenames."""
        safe = _SAFE_FILENAME_COMPONENT_RE.sub("_", value).strip("._-")
        return safe or "item"

    async def _run_pending_items(
        self,
        pending_items: list[BenchmarkItem],
        checkpoint: CheckpointState,
    ) -> None:
        """Run all pending items using a fixed-size worker pool."""
        if not pending_items:
            return

        work_queue: asyncio.Queue[BenchmarkItem | None] = asyncio.Queue()
        for item in pending_items:
            work_queue.put_nowait(item)

        n_workers = min(self.config.max_concurrent, len(pending_items))
        for _ in range(n_workers):
            work_queue.put_nowait(None)

        checkpoint_lock = asyncio.Lock()
        async with asyncio.TaskGroup() as tg:
            for _ in range(n_workers):
                tg.create_task(
                    self._run_worker(
                        work_queue=work_queue,
                        checkpoint=checkpoint,
                        checkpoint_lock=checkpoint_lock,
                    )
                )

    async def _run_worker(
        self,
        *,
        work_queue: asyncio.Queue[BenchmarkItem | None],
        checkpoint: CheckpointState,
        checkpoint_lock: asyncio.Lock,
    ) -> None:
        """Worker that processes items and updates checkpoints."""
        while True:
            item = await work_queue.get()
            try:
                if item is None:
                    return

                result = await self._run_single_item(item)

                async with checkpoint_lock:
                    checkpoint.results.append(result)
                    checkpoint.completed_ids.add(item.benchmark_id)

                    if (
                        len(checkpoint.completed_ids) % self.config.checkpoint_interval
                        == 0
                    ):
                        self._checkpoint_manager.save(checkpoint)
            finally:
                work_queue.task_done()

    async def _run_single_item(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run the GIANT agent on a single benchmark item.

        Args:
            item: BenchmarkItem to evaluate.

        Returns:
            BenchmarkResult with prediction and correctness.
        """
        try:
            # Configure agent
            agent_config = AgentConfig(
                max_steps=self.config.max_steps,
            )

            # Run agent (with majority voting if runs_per_item > 1)
            predictions = []
            labels: list[int | None] = []
            total_cost = 0.0
            total_tokens = 0
            last_trajectory_path = ""

            for run_idx in range(self.config.runs_per_item):
                agent = GIANTAgent(
                    wsi_path=item.wsi_path,
                    question=item.prompt,
                    llm_provider=self.llm_provider,
                    config=agent_config,
                )

                run_result = await agent.run()
                prediction_text = run_result.answer
                predictions.append(prediction_text)
                total_cost += run_result.total_cost
                total_tokens += run_result.total_tokens

                extracted = extract_label(
                    prediction_text,
                    benchmark_name=item.benchmark_name,
                    options=item.options,
                )
                labels.append(extracted.label)

                # Save trajectory
                if self.config.save_trajectories:
                    last_trajectory_path = self._save_trajectory(
                        item.benchmark_id,
                        run_idx,
                        run_result,
                    )

            # Apply majority voting if multiple runs
            final_prediction, final_label = self._select_majority_prediction(
                predictions=predictions,
                labels=labels,
            )

            # Determine correctness
            correct = final_label == item.truth_label

            return BenchmarkResult(
                item_id=item.benchmark_id,
                prediction=final_prediction,
                predicted_label=final_label,
                truth_label=item.truth_label,
                correct=correct,
                cost_usd=total_cost,
                total_tokens=total_tokens,
                trajectory_file=last_trajectory_path,
            )

        except Exception as e:
            logger.exception("Error running item %s", item.benchmark_id)
            return BenchmarkResult(
                item_id=item.benchmark_id,
                prediction="",
                predicted_label=None,
                truth_label=item.truth_label,
                correct=False,
                trajectory_file="",
                error=str(e),
            )

    def _majority_vote(self, predictions: list[str]) -> str:
        """Apply majority voting to multiple predictions.

        Args:
            predictions: List of prediction strings.

        Returns:
            Most common prediction.
        """
        counts = Counter(predictions)
        return counts.most_common(1)[0][0]

    def _select_majority_prediction(
        self,
        *,
        predictions: list[str],
        labels: list[int | None],
    ) -> tuple[str, int | None]:
        """Select final prediction for runs_per_item > 1.

        Voting policy:
        - If at least one run produced an extracted label, vote on labels.
          The returned prediction text is taken from the first run that matches
          the winning label (stable and deterministic).
        - If no run produced a label (all None), vote on raw prediction strings.
        """
        if len(predictions) != len(labels):
            raise ValueError("predictions and labels must have the same length")
        if not predictions:
            raise ValueError("predictions must not be empty")

        if len(predictions) == 1:
            return predictions[0], labels[0]

        if any(label is not None for label in labels):
            counts: Counter[int | None] = Counter(labels)
            max_count = max(counts.values())
            winners = {label for label, count in counts.items() if count == max_count}

            # Deterministic tie-break: first seen in input order.
            winning_label = next(label for label in labels if label in winners)

            winning_prediction = next(
                pred
                for pred, label in zip(predictions, labels, strict=True)
                if label == winning_label
            )
            return winning_prediction, winning_label

        return self._majority_vote(predictions), None

    def _compute_metrics(
        self,
        results: list[BenchmarkResult],
        benchmark_name: str,
    ) -> dict[str, Any]:
        """Compute evaluation metrics with bootstrap uncertainty.

        Args:
            results: List of benchmark results.
            benchmark_name: Name of the benchmark.

        Returns:
            Dictionary with metrics and bootstrap results.
        """
        if not results:
            return {"error": "No results to compute metrics"}

        # Paper-faithful scoring: failures to answer/extract count as incorrect.
        # Use a sentinel label that will never match any truth label.
        predictions: list[int] = [
            r.predicted_label
            if r.predicted_label is not None and r.error is None
            else _MISSING_LABEL_SENTINEL
            for r in results
        ]
        truths = [r.truth_label for r in results]

        # Determine metric type
        task_info = BENCHMARK_TASKS.get(benchmark_name, {})
        metric_type = task_info.get("metric", "accuracy")

        if metric_type == "balanced_accuracy":
            metric_fn = balanced_accuracy
            point_estimate = balanced_accuracy(predictions, truths)
        else:
            metric_fn = accuracy
            point_estimate = accuracy(predictions, truths)

        # Compute bootstrap
        bootstrap = bootstrap_metric(predictions, truths, metric_fn)

        return {
            "metric_type": metric_type,
            "point_estimate": point_estimate,
            "bootstrap_mean": bootstrap.mean,
            "bootstrap_std": bootstrap.std,
            "bootstrap_ci_lower": bootstrap.ci_lower,
            "bootstrap_ci_upper": bootstrap.ci_upper,
            "n_replicates": bootstrap.n_replicates,
            "n_total": len(results),
            "n_errors": sum(r.error is not None for r in results),
            "n_extraction_failures": sum(
                r.error is None and r.predicted_label is None for r in results
            ),
            "format_string": f"{bootstrap.mean:.1%} ± {bootstrap.std:.1%}",
        }

    def _save_trajectory(
        self,
        item_id: str,
        run_idx: int,
        run_result: RunResult,
    ) -> str:
        """Save trajectory to file.

        Args:
            item_id: Benchmark item ID.
            run_idx: Run index (for multiple runs).
            run_result: Result from agent run.

        Returns:
            Path to saved trajectory file.
        """
        trajectories_dir = self.output_dir / "trajectories"
        trajectories_dir.mkdir(exist_ok=True)

        safe_item_id = self._safe_filename_component(item_id)
        filename = f"{safe_item_id}_run{run_idx}.json"
        path = trajectories_dir / filename

        trajectory_data = run_result.trajectory.model_dump()
        path.write_text(json.dumps(trajectory_data, indent=2))

        return str(path)

    def _save_results(self, results: EvaluationResults) -> None:
        """Save final evaluation results.

        Args:
            results: Complete evaluation results.
        """
        results_path = self.output_dir / f"{results.run_id}_results.json"
        results_path.write_text(results.model_dump_json(indent=2))
        logger.info("Results saved to %s", results_path)
