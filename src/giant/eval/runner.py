"""Benchmark runner for batch evaluation (Spec-10).

Provides the BenchmarkRunner class that:
- Loads MultiPathQA benchmark items from CSV
- Resolves WSI paths under a user-provided wsi_root
- Runs the GIANT agent in batch mode with concurrency control
- Extracts and scores answers
- Saves results with full provenance
"""

from __future__ import annotations

import ast
import asyncio
import csv
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

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
from giant.eval.wsi_resolver import WSIPathResolver

if TYPE_CHECKING:
    from giant.llm.protocol import LLMProvider

logger = logging.getLogger(__name__)

_MISSING_LABEL_SENTINEL = -1

_SAFE_FILENAME_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


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


@dataclass(frozen=True)
class _ItemRunState:
    predictions: list[str]
    labels: list[int | None]
    total_cost: float
    total_tokens: int
    last_trajectory_path: str
    per_run_errors: list[str | None]


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
        self._wsi_resolver = WSIPathResolver(self.wsi_root)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_manager = CheckpointManager(self.output_dir / "checkpoints")

    def load_benchmark_items(
        self,
        csv_path: Path | str,
        benchmark_name: str,
        *,
        skip_missing_wsis: bool = False,
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
        missing_wsis = 0

        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Filter by benchmark name and validity
                if row.get("benchmark_name") != benchmark_name:
                    continue
                if row.get("is_valid", "True").lower() != "true":
                    continue

                benchmark_id = (
                    row.get("benchmark_id")
                    or row.get("id")  # legacy / test fixtures
                    or row.get("image_path")
                )
                if not benchmark_id:
                    raise ValueError("Missing benchmark_id in CSV row")

                file_id = row.get("file_id") or None

                # Resolve WSI path
                image_path = row["image_path"]
                try:
                    wsi_path = self._resolve_wsi_path(
                        image_path,
                        benchmark_name,
                        file_id=file_id,
                    )
                except FileNotFoundError:
                    if skip_missing_wsis:
                        missing_wsis += 1
                        continue
                    raise

                # Parse options if present
                options = None
                options_str = (row.get("options", "") or "").strip()
                if options_str:
                    options = self._parse_options(options_str)

                # Build prompt (substitute {options} if present, otherwise append)
                prompt = row.get("prompt", row.get("question", ""))
                if options:
                    prompt = self._inject_options(prompt, options)

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
                    benchmark_id=benchmark_id,
                    file_id=file_id,
                    image_path=image_path,
                    prompt=prompt,
                    options=options,
                    metric_type=str(task_info["metric"]),
                    truth_label=truth_label,
                    wsi_path=str(wsi_path),
                )
                items.append(item)

        logger.info(
            "Loaded %d items for benchmark %s (skipped %d missing WSIs)",
            len(items),
            benchmark_name,
            missing_wsis,
        )
        return items

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

        Args:
            image_path: Filename from CSV.
            benchmark_name: Benchmark name for subdirectory.
            file_id: Optional dataset identifier for locating downloaded files.

        Returns:
            Resolved path to WSI file.

        Raises:
            FileNotFoundError: If WSI file is not found.
            ValueError: If image_path attempts path traversal.
        """
        return self._wsi_resolver.resolve(
            image_path,
            benchmark_name,
            file_id=file_id,
        )

    @staticmethod
    def _parse_options(options_str: str) -> list[str]:
        """Parse the MultiPathQA `options` field into a list of strings.

        MultiPathQA stores options as either:
        - JSON list: ["A", "B"]
        - Python literal list: ['A', 'B']  (common in the released CSV)
        - Pipe-delimited string: A|B (legacy / test fixtures)

        Raises:
            ValueError: If options cannot be parsed into a list.
        """
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
                    raise ValueError(
                        f"Unparseable options field: {options_str!r}"
                    ) from e

        if isinstance(parsed, tuple):
            parsed = list(parsed)
        if not isinstance(parsed, list):
            raise ValueError(
                f"Options must be a list, got {type(parsed).__name__}: {options_str!r}"
            )

        cleaned = [str(opt).strip() for opt in parsed]
        return [opt for opt in cleaned if opt]

    @staticmethod
    def _inject_options(prompt: str, options: list[str]) -> str:
        formatted_options = "\n".join(
            f"{i}. {opt}" for i, opt in enumerate(options, start=1)
        )

        if "{options}" in prompt:
            return prompt.replace("{options}", formatted_options)

        return (
            f"{prompt}\n\n"
            f"Select from the following options:\n{formatted_options}\n\n"
            "Please respond with the option number (1-based index)."
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
        stop_event = asyncio.Event()
        budget_state = {"total_cost": sum(r.cost_usd for r in checkpoint.results)}
        if (
            self.config.budget_usd is not None
            and budget_state["total_cost"] >= self.config.budget_usd
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
                        budget_state=budget_state,
                    )
                )

    async def _run_worker(
        self,
        *,
        work_queue: asyncio.Queue[BenchmarkItem | None],
        checkpoint: CheckpointState,
        checkpoint_lock: asyncio.Lock,
        stop_event: asyncio.Event,
        budget_state: dict[str, float],
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

                result = await self._run_single_item(item)

                async with checkpoint_lock:
                    checkpoint.results.append(result)
                    checkpoint.completed_ids.add(item.benchmark_id)
                    budget_state["total_cost"] += result.cost_usd
                    if (
                        self.config.budget_usd is not None
                        and budget_state["total_cost"] >= self.config.budget_usd
                        and not stop_event.is_set()
                    ):
                        logger.warning(
                            "Budget reached, stopping early: %.4f >= %.4f",
                            budget_state["total_cost"],
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

    async def _run_single_item(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run a single benchmark item (mode-aware).

        Args:
            item: BenchmarkItem to evaluate.

        Returns:
            BenchmarkResult with prediction and correctness.
        """
        try:
            if self.config.mode == "giant":
                return await self._run_item_giant(item)
            if self.config.mode == "thumbnail":
                return await self._run_item_thumbnail(item)
            if self.config.mode == "patch":
                return await self._run_item_patch(item)
            raise ValueError(f"Unknown evaluation mode: {self.config.mode!r}")

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

    def _build_item_result(
        self,
        *,
        item: BenchmarkItem,
        state: _ItemRunState,
    ) -> BenchmarkResult:
        final_prediction, final_label = self._select_majority_prediction(
            predictions=state.predictions,
            labels=state.labels,
        )
        correct = final_label == item.truth_label
        error = None
        if final_label is None:
            error = next((e for e in state.per_run_errors if e), None)

        return BenchmarkResult(
            item_id=item.benchmark_id,
            prediction=final_prediction,
            predicted_label=final_label,
            truth_label=item.truth_label,
            correct=correct,
            cost_usd=state.total_cost,
            total_tokens=state.total_tokens,
            trajectory_file=state.last_trajectory_path,
            error=error,
        )

    async def _run_item_giant(self, item: BenchmarkItem) -> BenchmarkResult:
        agent_config = AgentConfig(
            max_steps=self.config.max_steps,
            strict_font_check=self.config.strict_font_check,
        )

        predictions: list[str] = []
        labels: list[int | None] = []
        per_run_errors: list[str | None] = []
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
            per_run_errors.append(run_result.error_message)

            prediction_text = run_result.answer
            predictions.append(prediction_text)
            total_cost += run_result.total_cost
            total_tokens += run_result.total_tokens

            if run_result.success:
                extracted = extract_label(
                    prediction_text,
                    benchmark_name=item.benchmark_name,
                    options=item.options,
                )
                labels.append(extracted.label)
            else:
                labels.append(None)

            if self.config.save_trajectories:
                last_trajectory_path = self._save_trajectory(
                    item.benchmark_id,
                    run_idx,
                    run_result,
                )

        state = _ItemRunState(
            predictions=predictions,
            labels=labels,
            total_cost=total_cost,
            total_tokens=total_tokens,
            last_trajectory_path=last_trajectory_path,
            per_run_errors=per_run_errors,
        )
        return self._build_item_result(item=item, state=state)

    async def _run_item_thumbnail(self, item: BenchmarkItem) -> BenchmarkResult:
        from giant.core.baselines import (  # noqa: PLC0415
            BaselineRequest,
            encode_image_to_base64,
            run_baseline_answer,
        )
        from giant.wsi.reader import WSIReader  # noqa: PLC0415

        with WSIReader(item.wsi_path) as reader:
            thumbnail = reader.get_thumbnail((1024, 1024))

        image_b64, media_type = encode_image_to_base64(thumbnail)
        request = BaselineRequest(
            wsi_path=Path(item.wsi_path),
            question=item.prompt,
            image_base64=image_b64,
            media_type=media_type,
            context_note="This is a whole-slide thumbnail (no navigation).",
        )

        predictions: list[str] = []
        labels: list[int | None] = []
        per_run_errors: list[str | None] = []
        total_cost = 0.0
        total_tokens = 0
        last_trajectory_path = ""

        for run_idx in range(self.config.runs_per_item):
            run_result = await run_baseline_answer(
                llm_provider=self.llm_provider,
                request=request,
            )
            per_run_errors.append(run_result.error_message)

            predictions.append(run_result.answer)
            total_cost += run_result.total_cost
            total_tokens += run_result.total_tokens

            if run_result.success:
                extracted = extract_label(
                    run_result.answer,
                    benchmark_name=item.benchmark_name,
                    options=item.options,
                )
                labels.append(extracted.label)
            else:
                labels.append(None)

            if self.config.save_trajectories:
                last_trajectory_path = self._save_trajectory(
                    item.benchmark_id,
                    run_idx,
                    run_result,
                )

        state = _ItemRunState(
            predictions=predictions,
            labels=labels,
            total_cost=total_cost,
            total_tokens=total_tokens,
            last_trajectory_path=last_trajectory_path,
            per_run_errors=per_run_errors,
        )
        return self._build_item_result(item=item, state=state)

    async def _run_item_patch(self, item: BenchmarkItem) -> BenchmarkResult:
        from giant.core.baselines import (  # noqa: PLC0415
            BaselineRequest,
            encode_image_to_base64,
            make_patch_collage,
            run_baseline_answer,
        )
        from giant.vision import (  # noqa: PLC0415
            N_PATCHES,
            PATCH_SIZE,
            TissueSegmentor,
            sample_patches,
        )
        from giant.wsi.reader import WSIReader  # noqa: PLC0415

        with WSIReader(item.wsi_path) as reader:
            meta = reader.get_metadata()
            thumbnail = reader.get_thumbnail((2048, 2048))

            segmentor = TissueSegmentor()
            mask = segmentor.segment(thumbnail)
            regions = sample_patches(
                mask,
                meta,
                n_patches=N_PATCHES,
                patch_size=PATCH_SIZE,
            )
            patch_images = [
                reader.read_region((r.x, r.y), 0, (r.width, r.height)) for r in regions
            ]

        collage = make_patch_collage(patch_images, patch_size=PATCH_SIZE)
        image_b64, media_type = encode_image_to_base64(collage)
        request = BaselineRequest(
            wsi_path=Path(item.wsi_path),
            question=item.prompt,
            image_base64=image_b64,
            media_type=media_type,
            context_note=(
                "This image is a montage of 30 random 224x224 tissue patches sampled "
                "from the slide."
            ),
        )

        predictions: list[str] = []
        labels: list[int | None] = []
        per_run_errors: list[str | None] = []
        total_cost = 0.0
        total_tokens = 0
        last_trajectory_path = ""

        for run_idx in range(self.config.runs_per_item):
            run_result = await run_baseline_answer(
                llm_provider=self.llm_provider,
                request=request,
            )
            per_run_errors.append(run_result.error_message)

            predictions.append(run_result.answer)
            total_cost += run_result.total_cost
            total_tokens += run_result.total_tokens

            if run_result.success:
                extracted = extract_label(
                    run_result.answer,
                    benchmark_name=item.benchmark_name,
                    options=item.options,
                )
                labels.append(extracted.label)
            else:
                labels.append(None)

            if self.config.save_trajectories:
                last_trajectory_path = self._save_trajectory(
                    item.benchmark_id,
                    run_idx,
                    run_result,
                )

        state = _ItemRunState(
            predictions=predictions,
            labels=labels,
            total_cost=total_cost,
            total_tokens=total_tokens,
            last_trajectory_path=last_trajectory_path,
            per_run_errors=per_run_errors,
        )
        return self._build_item_result(item=item, state=state)

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
