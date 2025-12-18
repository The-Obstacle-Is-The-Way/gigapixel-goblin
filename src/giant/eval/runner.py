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
                truth_label = self._parse_truth_label(
                    row.get("answer", ""),
                    benchmark_name,
                    options,
                )

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
        """
        # Try direct path
        direct_path = self.wsi_root / image_path
        if direct_path.exists():
            return direct_path

        # Try benchmark subdirectory
        subdir_path = self.wsi_root / benchmark_name / image_path
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

        # Try integer conversion first
        try:
            return int(answer)
        except ValueError:
            pass

        # GTEx: string label to index
        if options:
            try:
                idx = options.index(answer)
                return idx + 1  # 1-based
            except ValueError:
                pass

            # Case-insensitive match
            answer_lower = answer.lower()
            for i, opt in enumerate(options, start=1):
                if opt.lower() == answer_lower:
                    return i

        # Fallback: return 0 (will be incorrect)
        logger.warning(
            "Could not parse truth label '%s' for benchmark %s",
            answer,
            benchmark_name,
        )
        return 0

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

        # Run agent on pending items with concurrency control
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        tasks = [
            self._run_item_with_semaphore(item, semaphore, checkpoint)
            for item in pending_items
        ]

        await asyncio.gather(*tasks)

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

    async def _run_item_with_semaphore(
        self,
        item: BenchmarkItem,
        semaphore: asyncio.Semaphore,
        checkpoint: CheckpointState,
    ) -> None:
        """Run a single item with semaphore for concurrency control."""
        async with semaphore:
            result = await self._run_single_item(item)

            # Update checkpoint
            checkpoint.results.append(result)
            checkpoint.completed_ids.add(item.benchmark_id)

            # Save checkpoint periodically
            if len(checkpoint.completed_ids) % self.config.checkpoint_interval == 0:
                self._checkpoint_manager.save(checkpoint)

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
                predictions.append(run_result.answer)
                total_cost += run_result.total_cost
                total_tokens += run_result.total_tokens

                # Save trajectory
                if self.config.save_trajectories:
                    last_trajectory_path = self._save_trajectory(
                        item.benchmark_id,
                        run_idx,
                        run_result,
                    )

            # Apply majority voting if multiple runs
            if len(predictions) > 1:
                final_prediction = self._majority_vote(predictions)
            else:
                final_prediction = predictions[0]

            # Extract label from prediction
            extracted = extract_label(
                final_prediction,
                benchmark_name=item.benchmark_name,
                options=item.options,
            )

            # Determine correctness
            correct = extracted.label == item.truth_label

            return BenchmarkResult(
                item_id=item.benchmark_id,
                prediction=final_prediction,
                predicted_label=extracted.label,
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
        # Filter out errors
        valid_results = [
            r for r in results if r.error is None and r.predicted_label is not None
        ]

        if not valid_results:
            return {"error": "No valid results to compute metrics"}

        # We filtered out None values above, so we can safely cast
        predictions: list[int] = [
            r.predicted_label for r in valid_results if r.predicted_label is not None
        ]
        truths = [r.truth_label for r in valid_results]

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
            "n_valid": len(valid_results),
            "n_errors": len(results) - len(valid_results),
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

        filename = f"{item_id}_run{run_idx}.json"
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
