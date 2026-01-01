"""Benchmark evaluation orchestrator for batch runs (Spec-10).

This module provides:
- `EvaluationOrchestrator` (preferred): coordinates loading, execution, and
  persistence for a benchmark run.
- `BenchmarkRunner`: backwards-compatible alias for `EvaluationOrchestrator`.

Core responsibilities are split into focused modules:
- `giant.eval.loader` (CSV parsing and item construction)
- `giant.eval.executor` (per-item execution for each mode)
- `giant.eval.persistence` (filesystem writes)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator

from giant.data.schemas import BENCHMARK_TASKS, BenchmarkItem, BenchmarkResult
from giant.eval.executor import ItemExecutor
from giant.eval.loader import BenchmarkItemLoader
from giant.eval.metrics import (
    accuracy,
    balanced_accuracy,
    bootstrap_metric,
)
from giant.eval.persistence import ResultsPersistence
from giant.eval.resumable import CheckpointManager, CheckpointState
from giant.eval.wsi_resolver import WSIPathResolver
from giant.utils.logging import get_logger

if TYPE_CHECKING:
    from giant.llm.protocol import LLMProvider

logger = get_logger(__name__)

_MISSING_LABEL_SENTINEL = -1


class EvaluationConfig(BaseModel):
    """Configuration for benchmark evaluation.

    Attributes:
        mode: Evaluation mode ("giant", "thumbnail", "patch").
        max_steps: Maximum navigation steps per item (default: 20 per paper).
        runs_per_item: Number of runs per item for majority voting (default: 1).
        max_concurrent: Maximum concurrent agent runs.
        max_items: Optional cap on number of items to evaluate (useful for smoke tests).
        skip_missing_wsis: If True, skip CSV rows whose WSI is not present under
            wsi_root.
        budget_usd: Optional total budget across the whole run (stop early once
            exceeded).
        strict_font_check: If True, fail if axis label fonts are missing.
        save_trajectories: Whether to save full trajectories.
        checkpoint_interval: Save checkpoint every N items.
    """

    mode: Literal["giant", "thumbnail", "patch"] = Field(default="giant")
    max_steps: int = Field(default=20, ge=1)
    runs_per_item: int = Field(default=1, ge=1)
    max_concurrent: int = Field(default=4, ge=1)
    max_items: int | None = Field(default=None)
    skip_missing_wsis: bool = False
    budget_usd: float | None = Field(default=None, ge=0.0)
    strict_font_check: bool = Field(default=False)
    save_trajectories: bool = True
    checkpoint_interval: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def _validate_budget_requires_single_worker(self) -> EvaluationConfig:
        if self.budget_usd is not None and self.max_concurrent != 1:
            raise ValueError(
                "When budget_usd is set, max_concurrent must be 1 to avoid "
                "unbounded budget overruns from concurrent in-flight items."
            )
        return self


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


class EvaluationOrchestrator:
    """Orchestrates benchmark evaluation workflow (Spec-10)."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        wsi_root: Path | str,
        output_dir: Path | str,
        config: EvaluationConfig | None = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.wsi_root = Path(wsi_root)
        self.output_dir = Path(output_dir)
        self.config = config or EvaluationConfig()

        self._wsi_resolver = WSIPathResolver(self.wsi_root)
        self._persistence = ResultsPersistence(self.output_dir)
        self._executor = ItemExecutor(
            llm_provider=self.llm_provider,
            config=self.config,
            persistence=self._persistence,
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_manager = CheckpointManager(self.output_dir / "checkpoints")

    def load_benchmark_items(
        self,
        csv_path: Path | str,
        benchmark_name: str,
        *,
        skip_missing_wsis: bool = False,
    ) -> list[BenchmarkItem]:
        """Load benchmark items from MultiPathQA CSV."""
        loader = BenchmarkItemLoader(
            csv_path=Path(csv_path),
            wsi_resolver=self._wsi_resolver,
            benchmark_name=benchmark_name,
            skip_missing_wsis=skip_missing_wsis,
        )
        return loader.load()

    def _resolve_wsi_path(
        self,
        image_path: str,
        benchmark_name: str,
        *,
        file_id: str | None = None,
    ) -> Path:
        """Resolve WSI path under wsi_root.

        This wrapper exists for legacy call-sites and unit tests. The core path
        resolution logic lives in `WSIPathResolver`.
        """
        return self._wsi_resolver.resolve(
            image_path,
            benchmark_name,
            file_id=file_id,
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
        self._persistence.validate_run_id(run_id)

        # Load items
        items = self.load_benchmark_items(
            csv_path,
            benchmark_name,
            skip_missing_wsis=self.config.skip_missing_wsis,
        )

        # Load or create checkpoint
        checkpoint = self._checkpoint_manager.load_or_create(
            run_id,
            benchmark_name,
            config=self.config.model_dump(),
            model_name=self.llm_provider.get_model_name(),
            provider_name=self.llm_provider.get_provider_name(),
        )

        # Filter out completed items
        pending_items = [
            item for item in items if item.benchmark_id not in checkpoint.completed_ids
        ]
        if self.config.max_items is not None:
            if self.config.max_items < 1:
                raise ValueError("config.max_items must be >= 1 when provided")
            pending_items = pending_items[: self.config.max_items]

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
        self._persistence.save_results(results)

        return results

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
        stop_event = asyncio.Event()
        budget_tracker = {"total_cost": sum(r.cost_usd for r in checkpoint.results)}
        if (
            self.config.budget_usd is not None
            and budget_tracker["total_cost"] >= self.config.budget_usd
        ):
            stop_event.set()

        async with asyncio.TaskGroup() as tg:
            for _ in range(n_workers):
                tg.create_task(
                    self._run_worker(
                        work_queue=work_queue,
                        checkpoint=checkpoint,
                        checkpoint_lock=checkpoint_lock,
                        stop_event=stop_event,
                        budget_tracker=budget_tracker,
                    )
                )

    async def _run_worker(
        self,
        *,
        work_queue: asyncio.Queue[BenchmarkItem | None],
        checkpoint: CheckpointState,
        checkpoint_lock: asyncio.Lock,
        stop_event: asyncio.Event,
        budget_tracker: dict[str, float],
    ) -> None:
        """Worker that processes items and updates checkpoints.

        Uses atomic budget check under lock to prevent race conditions (C3 fix).
        """
        while True:
            item = await work_queue.get()
            try:
                if item is None:
                    return

                # C3 fix: Check stop_event under lock for atomic budget enforcement
                async with checkpoint_lock:
                    if stop_event.is_set():
                        continue

                result = await self._executor.run_single_item(item)

                async with checkpoint_lock:
                    checkpoint.results.append(result)
                    checkpoint.completed_ids.add(item.benchmark_id)
                    budget_tracker["total_cost"] += result.cost_usd
                    if (
                        self.config.budget_usd is not None
                        and budget_tracker["total_cost"] >= self.config.budget_usd
                        and not stop_event.is_set()
                    ):
                        logger.warning(
                            "Budget reached, stopping early: %.4f >= %.4f",
                            budget_tracker["total_cost"],
                            self.config.budget_usd,
                        )
                        stop_event.set()

                    if (
                        len(checkpoint.completed_ids) % self.config.checkpoint_interval
                        == 0
                    ):
                        self._checkpoint_manager.save(checkpoint)
            finally:
                work_queue.task_done()

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
        if any(truth == _MISSING_LABEL_SENTINEL for truth in truths):
            raise ValueError(
                "Truth labels contain the missing-label sentinel (-1). This "
                "collides with _MISSING_LABEL_SENTINEL used for extraction failures."
            )

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


BenchmarkRunner = EvaluationOrchestrator
