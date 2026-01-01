"""Item execution utilities for benchmark evaluation (Spec-10)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from giant.agent.runner import AgentConfig, GIANTAgent, RunResult
from giant.data.schemas import BenchmarkItem, BenchmarkResult
from giant.eval.answer_extraction import extract_label
from giant.eval.persistence import ResultsPersistence
from giant.utils.logging import get_logger

if TYPE_CHECKING:
    from giant.agent.trajectory import Turn
    from giant.core.baselines import BaselineRequest
    from giant.eval.runner import EvaluationConfig
    from giant.geometry.primitives import Region
    from giant.llm.protocol import LLMProvider

logger = get_logger(__name__)


@dataclass(frozen=True)
class _ItemRunState:
    predictions: list[str]
    labels: list[int | None]
    total_cost: float
    total_tokens: int
    last_trajectory_path: str
    per_run_errors: list[str | None]


@dataclass
class ItemExecutor:
    """Execute evaluation modes (giant/thumbnail/patch) for individual items."""

    llm_provider: LLMProvider
    config: EvaluationConfig
    persistence: ResultsPersistence

    async def run_single_item(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run a single benchmark item (mode-aware)."""
        try:
            if self.config.mode == "giant":
                return await self._run_item_giant(item)
            if self.config.mode == "thumbnail":
                return await self._run_item_thumbnail(item)
            if self.config.mode == "patch":
                return await self._run_item_patch(item)
            if self.config.mode == "patch_vote":
                return await self._run_item_patch_vote(item)
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
            enforce_fixed_iterations=self.config.enforce_fixed_iterations,
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
                last_trajectory_path = self.persistence.save_trajectory(
                    run_result=run_result,
                    item_id=item.benchmark_id,
                    run_idx=run_idx,
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
            run_result: RunResult = await run_baseline_answer(
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
                last_trajectory_path = self.persistence.save_trajectory(
                    run_result=run_result,
                    item_id=item.benchmark_id,
                    run_idx=run_idx,
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
            run_result: RunResult = await run_baseline_answer(
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
                last_trajectory_path = self.persistence.save_trajectory(
                    run_result=run_result,
                    item_id=item.benchmark_id,
                    run_idx=run_idx,
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

    def _prepare_patch_vote_requests(
        self, item: BenchmarkItem
    ) -> tuple[list[Region], list[BaselineRequest]]:
        from giant.core.baselines import (  # noqa: PLC0415
            BaselineRequest,
            encode_image_to_base64,
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

            mask = TissueSegmentor().segment(thumbnail)
            regions = sample_patches(
                mask,
                meta,
                n_patches=N_PATCHES,
                patch_size=PATCH_SIZE,
            )
            patch_images = [
                reader.read_region((r.x, r.y), 0, (r.width, r.height)) for r in regions
            ]

        patch_requests: list[BaselineRequest] = []
        for patch_idx, patch in enumerate(patch_images):
            image_b64, media_type = encode_image_to_base64(patch)
            patch_requests.append(
                BaselineRequest(
                    wsi_path=Path(item.wsi_path),
                    question=item.prompt,
                    image_base64=image_b64,
                    media_type=media_type,
                    context_note=(
                        f"This image is patch {patch_idx + 1} of {N_PATCHES} random "
                        f"{PATCH_SIZE}x{PATCH_SIZE} tissue patches sampled from "
                        "the slide."
                    ),
                )
            )

        return regions, patch_requests

    async def _run_patch_vote_single_run(
        self,
        *,
        item: BenchmarkItem,
        regions: list[Region],
        patch_requests: list[BaselineRequest],
    ) -> tuple[str, int | None, float, int, str | None, list[Turn]]:
        from giant.agent.trajectory import Turn  # noqa: PLC0415
        from giant.core.baselines import run_baseline_answer  # noqa: PLC0415

        patch_predictions: list[str] = []
        patch_labels: list[int | None] = []
        patch_errors: list[str | None] = []
        patch_turns: list[Turn] = []
        run_cost = 0.0
        run_tokens = 0

        for patch_idx, request in enumerate(patch_requests):
            patch_result: RunResult = await run_baseline_answer(
                llm_provider=self.llm_provider,
                request=request,
            )
            patch_errors.append(patch_result.error_message)
            patch_predictions.append(patch_result.answer)
            run_cost += patch_result.total_cost
            run_tokens += patch_result.total_tokens

            if patch_result.success:
                extracted = extract_label(
                    patch_result.answer,
                    benchmark_name=item.benchmark_name,
                    options=item.options,
                )
                patch_labels.append(extracted.label)
            else:
                patch_labels.append(None)

            if patch_result.trajectory.turns:
                patch_turns.append(
                    Turn(
                        step_index=len(patch_turns),
                        image_base64=request.image_base64,
                        response=patch_result.trajectory.turns[0].response,
                        region=regions[patch_idx],
                    )
                )

        final_prediction, final_label = self._select_majority_prediction(
            predictions=patch_predictions,
            labels=patch_labels,
        )
        run_error = next((e for e in patch_errors if e), None)
        return (
            final_prediction,
            final_label,
            run_cost,
            run_tokens,
            run_error,
            patch_turns,
        )

    async def _run_item_patch_vote(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run patch baseline with per-patch majority vote (paper-fidelity)."""
        from giant.agent.runner import RunResult  # noqa: PLC0415
        from giant.agent.trajectory import Trajectory  # noqa: PLC0415

        regions, patch_requests = self._prepare_patch_vote_requests(item)

        predictions: list[str] = []
        labels: list[int | None] = []
        per_run_errors: list[str | None] = []
        total_cost = 0.0
        total_tokens = 0
        last_trajectory_path = ""

        for run_idx in range(self.config.runs_per_item):
            (
                final_prediction,
                final_label,
                run_cost,
                run_tokens,
                run_error,
                patch_turns,
            ) = await self._run_patch_vote_single_run(
                item=item,
                regions=regions,
                patch_requests=patch_requests,
            )

            predictions.append(final_prediction)
            labels.append(final_label)
            per_run_errors.append(run_error)
            total_cost += run_cost
            total_tokens += run_tokens

            if self.config.save_trajectories:
                trajectory = Trajectory(
                    wsi_path=str(item.wsi_path),
                    question=item.prompt,
                    turns=patch_turns,
                    final_answer=final_prediction,
                )
                aggregated_run = RunResult(
                    answer=final_prediction,
                    trajectory=trajectory,
                    total_tokens=run_tokens,
                    total_cost=run_cost,
                    success=final_label is not None,
                    error_message=run_error if final_label is None else None,
                )
                last_trajectory_path = self.persistence.save_trajectory(
                    run_result=aggregated_run,
                    item_id=item.benchmark_id,
                    run_idx=run_idx,
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

    @staticmethod
    def _majority_vote(predictions: list[str]) -> str:
        counts = Counter(predictions)
        return counts.most_common(1)[0][0]

    @classmethod
    def _select_majority_prediction(
        cls,
        *,
        predictions: list[str],
        labels: list[int | None],
    ) -> tuple[str, int | None]:
        if len(predictions) != len(labels):
            raise ValueError("predictions and labels must have the same length")
        if not predictions:
            raise ValueError("predictions must not be empty")

        if len(predictions) == 1:
            return predictions[0], labels[0]

        valid_labels = [label for label in labels if label is not None]
        if valid_labels:
            counts: Counter[int] = Counter(valid_labels)
            max_count = max(counts.values())
            winners = {label for label, count in counts.items() if count == max_count}

            winning_label: int = next(label for label in labels if label in winners)

            winning_prediction = next(
                pred
                for pred, label in zip(predictions, labels, strict=True)
                if label == winning_label
            )
            return winning_prediction, winning_label

        return cls._majority_vote(predictions), None
