"""Tests for giant.eval.executor module (Spec-10).

These tests verify the ItemExecutor class that handles mode-specific
execution for benchmark evaluation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from giant.agent.runner import RunResult
from giant.agent.trajectory import Trajectory
from giant.data.schemas import BenchmarkItem
from giant.eval.executor import ItemExecutor, _ItemRunState
from giant.eval.persistence import ResultsPersistence
from giant.eval.runner import EvaluationConfig
from giant.geometry.primitives import Region
from giant.llm.protocol import FinalAnswerAction, LLMResponse, StepResponse, TokenUsage


def _make_benchmark_item(  # noqa: PLR0913
    *,
    benchmark_id: str = "TEST-001",
    benchmark_name: str = "tcga",
    prompt: str = "What is this?",
    options: list[str] | None = None,
    truth_label: int = 1,
    wsi_path: str = "/path/to/slide.svs",
    image_path: str = "slide.svs",
    metric_type: str = "accuracy",
) -> BenchmarkItem:
    """Create a BenchmarkItem for testing."""
    return BenchmarkItem(
        benchmark_name=benchmark_name,
        benchmark_id=benchmark_id,
        image_path=image_path,
        prompt=prompt,
        options=options or ["Lung", "Breast", "Colon"],
        metric_type=metric_type,
        truth_label=truth_label,
        wsi_path=wsi_path,
    )


def _make_run_result(
    *,
    answer: str = "Lung",
    success: bool = True,
    error_message: str | None = None,
    total_tokens: int = 100,
    total_cost: float = 0.01,
) -> RunResult:
    """Create a RunResult for testing."""
    trajectory = Trajectory(
        wsi_path="/path/to/slide.svs",
        question="What is this?",
        turns=[],
        final_answer=answer if success else None,
    )
    return RunResult(
        answer=answer,
        trajectory=trajectory,
        total_tokens=total_tokens,
        total_cost=total_cost,
        success=success,
        error_message=error_message,
    )


@pytest.fixture
def mock_provider() -> MagicMock:
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.get_model_name.return_value = "gpt-5.2"
    provider.get_provider_name.return_value = "openai"
    return provider


@pytest.fixture
def mock_persistence(tmp_path: Path) -> ResultsPersistence:
    """Create a real persistence instance with a temp directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return ResultsPersistence(output_dir=output_dir)


@pytest.fixture
def config() -> EvaluationConfig:
    """Create a default evaluation config."""
    return EvaluationConfig(
        mode="giant",
        max_steps=5,
        runs_per_item=1,
        save_trajectories=True,
    )


@pytest.fixture
def executor(
    mock_provider: MagicMock,
    config: EvaluationConfig,
    mock_persistence: ResultsPersistence,
) -> ItemExecutor:
    """Create an ItemExecutor instance for testing."""
    return ItemExecutor(
        llm_provider=mock_provider,
        config=config,
        persistence=mock_persistence,
    )


class TestItemRunState:
    """Tests for the _ItemRunState dataclass."""

    def test_is_immutable(self) -> None:
        """Verify _ItemRunState is frozen."""
        state = _ItemRunState(
            predictions=["A"],
            labels=[1],
            total_cost=0.01,
            total_tokens=100,
            last_trajectory_path="/path/to/traj.json",
            per_run_errors=[None],
        )
        with pytest.raises(AttributeError):
            state.predictions = ["B"]  # type: ignore[misc]


class TestRunSingleItem:
    """Tests for ItemExecutor.run_single_item method."""

    @pytest.mark.asyncio
    async def test_dispatches_to_giant_mode(
        self, executor: ItemExecutor, mock_persistence: ResultsPersistence
    ) -> None:
        """Verify giant mode calls _run_item_giant."""
        item = _make_benchmark_item()

        with patch.object(
            executor,
            "_run_item_giant",
            new_callable=AsyncMock,
        ) as mock_giant:
            mock_giant.return_value = MagicMock()
            executor.config = EvaluationConfig(mode="giant")
            await executor.run_single_item(item)
            mock_giant.assert_called_once_with(item)

    @pytest.mark.asyncio
    async def test_dispatches_to_thumbnail_mode(self, executor: ItemExecutor) -> None:
        """Verify thumbnail mode calls _run_item_thumbnail."""
        item = _make_benchmark_item()

        executor.config = EvaluationConfig(mode="thumbnail")
        with patch.object(
            executor,
            "_run_item_thumbnail",
            new_callable=AsyncMock,
        ) as mock_thumb:
            mock_thumb.return_value = MagicMock()
            await executor.run_single_item(item)
            mock_thumb.assert_called_once_with(item)

    @pytest.mark.asyncio
    async def test_dispatches_to_patch_mode(self, executor: ItemExecutor) -> None:
        """Verify patch mode calls _run_item_patch."""
        item = _make_benchmark_item()

        executor.config = EvaluationConfig(mode="patch")
        with patch.object(
            executor,
            "_run_item_patch",
            new_callable=AsyncMock,
        ) as mock_patch:
            mock_patch.return_value = MagicMock()
            await executor.run_single_item(item)
            mock_patch.assert_called_once_with(item)

    @pytest.mark.asyncio
    async def test_dispatches_to_patch_vote_mode(self, executor: ItemExecutor) -> None:
        """Verify patch_vote mode calls _run_item_patch_vote."""
        item = _make_benchmark_item()

        executor.config = EvaluationConfig(mode="patch_vote")
        with patch.object(
            executor,
            "_run_item_patch_vote",
            new_callable=AsyncMock,
        ) as mock_vote:
            mock_vote.return_value = MagicMock()
            await executor.run_single_item(item)
            mock_vote.assert_called_once_with(item)

    @pytest.mark.asyncio
    async def test_returns_error_result_on_exception(
        self, executor: ItemExecutor
    ) -> None:
        """Verify exceptions are caught and returned as error results."""
        item = _make_benchmark_item(benchmark_id="ERROR-001", truth_label=2)

        with patch.object(
            executor,
            "_run_item_giant",
            new_callable=AsyncMock,
        ) as mock_giant:
            mock_giant.side_effect = RuntimeError("Simulated failure")
            result = await executor.run_single_item(item)

        assert result.item_id == "ERROR-001"
        assert result.error == "Simulated failure"
        assert result.predicted_label is None
        assert result.truth_label == 2
        assert result.correct is False

    @pytest.mark.asyncio
    async def test_unknown_mode_raises_value_error(
        self, executor: ItemExecutor
    ) -> None:
        """Verify unknown mode raises ValueError."""
        item = _make_benchmark_item()

        # Use object.__setattr__ to bypass frozen dataclass
        object.__setattr__(executor.config, "mode", "unknown")  # type: ignore[arg-type]

        result = await executor.run_single_item(item)
        assert "Unknown evaluation mode" in (result.error or "")


class TestBuildItemResult:
    """Tests for ItemExecutor._build_item_result method."""

    def test_builds_correct_result_single_run(self, executor: ItemExecutor) -> None:
        """Verify correct result for single successful run."""
        item = _make_benchmark_item(truth_label=1)
        state = _ItemRunState(
            predictions=["Lung"],
            labels=[1],
            total_cost=0.01,
            total_tokens=100,
            last_trajectory_path="/path/to/traj.json",
            per_run_errors=[None],
        )

        result = executor._build_item_result(item=item, state=state)

        assert result.item_id == item.benchmark_id
        assert result.prediction == "Lung"
        assert result.predicted_label == 1
        assert result.truth_label == 1
        assert result.correct is True
        assert result.cost_usd == 0.01
        assert result.total_tokens == 100
        assert result.trajectory_file == "/path/to/traj.json"
        assert result.error is None

    def test_builds_incorrect_result(self, executor: ItemExecutor) -> None:
        """Verify incorrect result when prediction doesn't match truth."""
        item = _make_benchmark_item(truth_label=2)
        state = _ItemRunState(
            predictions=["Lung"],
            labels=[1],
            total_cost=0.01,
            total_tokens=100,
            last_trajectory_path="",
            per_run_errors=[None],
        )

        result = executor._build_item_result(item=item, state=state)

        assert result.correct is False
        assert result.predicted_label == 1
        assert result.truth_label == 2

    def test_includes_error_when_label_is_none(self, executor: ItemExecutor) -> None:
        """Verify error is included when final label is None."""
        item = _make_benchmark_item()
        state = _ItemRunState(
            predictions=["???"],
            labels=[None],
            total_cost=0.01,
            total_tokens=100,
            last_trajectory_path="",
            per_run_errors=["Failed to extract label"],
        )

        result = executor._build_item_result(item=item, state=state)

        assert result.predicted_label is None
        assert result.error == "Failed to extract label"
        assert result.correct is False


class TestRunItemGiant:
    """Tests for ItemExecutor._run_item_giant method."""

    @pytest.mark.asyncio
    async def test_runs_giant_agent_and_extracts_label(
        self, executor: ItemExecutor
    ) -> None:
        """Verify GIANT agent is run and label is extracted."""
        item = _make_benchmark_item(
            benchmark_name="tcga",
            options=["Lung", "Breast", "Colon"],
            truth_label=1,
        )
        run_result = _make_run_result(answer="Lung", success=True)

        with (
            patch("giant.eval.executor.GIANTAgent") as mock_agent_class,
            patch("giant.eval.executor.extract_label") as mock_extract,
        ):
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=run_result)
            mock_agent_class.return_value = mock_agent_instance

            mock_extract.return_value = MagicMock(label=1)

            result = await executor._run_item_giant(item)

        mock_agent_class.assert_called_once()
        mock_agent_instance.run.assert_called_once()
        mock_extract.assert_called_once_with(
            "Lung",
            benchmark_name="tcga",
            options=["Lung", "Breast", "Colon"],
        )
        assert result.predicted_label == 1
        assert result.correct is True

    @pytest.mark.asyncio
    async def test_handles_failed_run(self, executor: ItemExecutor) -> None:
        """Verify failed runs set label to None."""
        item = _make_benchmark_item()
        run_result = _make_run_result(
            answer="",
            success=False,
            error_message="Navigation failed",
        )

        with patch("giant.eval.executor.GIANTAgent") as mock_agent_class:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=run_result)
            mock_agent_class.return_value = mock_agent_instance

            result = await executor._run_item_giant(item)

        assert result.predicted_label is None
        assert result.error == "Navigation failed"

    @pytest.mark.asyncio
    async def test_saves_trajectory(
        self, executor: ItemExecutor, mock_persistence: ResultsPersistence
    ) -> None:
        """Verify trajectory is saved when save_trajectories is enabled."""
        item = _make_benchmark_item(benchmark_id="TRAJ-001")
        run_result = _make_run_result(answer="Lung", success=True)

        with (
            patch("giant.eval.executor.GIANTAgent") as mock_agent_class,
            patch("giant.eval.executor.extract_label") as mock_extract,
        ):
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=run_result)
            mock_agent_class.return_value = mock_agent_instance
            mock_extract.return_value = MagicMock(label=1)

            result = await executor._run_item_giant(item)

        assert "TRAJ-001" in result.trajectory_file
        assert result.trajectory_file.endswith(".json")

    @pytest.mark.asyncio
    async def test_multiple_runs_accumulate_costs(self, executor: ItemExecutor) -> None:
        """Verify multiple runs accumulate tokens and costs."""
        executor.config = EvaluationConfig(
            mode="giant",
            runs_per_item=3,
            save_trajectories=False,
        )
        item = _make_benchmark_item()
        run_result = _make_run_result(
            answer="Lung",
            success=True,
            total_tokens=100,
            total_cost=0.01,
        )

        with (
            patch("giant.eval.executor.GIANTAgent") as mock_agent_class,
            patch("giant.eval.executor.extract_label") as mock_extract,
        ):
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=run_result)
            mock_agent_class.return_value = mock_agent_instance
            mock_extract.return_value = MagicMock(label=1)

            result = await executor._run_item_giant(item)

        assert result.total_tokens == 300  # 3 runs * 100 tokens
        assert result.cost_usd == pytest.approx(0.03)  # 3 runs * 0.01


class TestRunItemPatchVote:
    @pytest.mark.asyncio
    async def test_patch_vote_calls_provider_30x_and_majority_votes(
        self,
        tmp_path: Path,
    ) -> None:
        """Patch-vote baseline should perform per-patch calls (BUG-042)."""
        from PIL import Image

        provider = MagicMock()
        provider.get_model_name.return_value = "gpt-5.2"
        provider.get_provider_name.return_value = "openai"
        provider.generate_response = AsyncMock()

        def make_llm_answer(answer: str) -> LLMResponse:
            return LLMResponse(
                step_response=StepResponse(
                    reasoning="Patch analysis",
                    action=FinalAnswerAction(answer_text=answer),
                ),
                usage=TokenUsage(
                    prompt_tokens=1,
                    completion_tokens=1,
                    total_tokens=2,
                    cost_usd=0.001,
                ),
                model="gpt-5.2",
                latency_ms=1.0,
            )

        provider.generate_response.side_effect = [
            *[make_llm_answer("Lung") for _ in range(20)],
            *[make_llm_answer("Breast") for _ in range(10)],
        ]

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        persistence = ResultsPersistence(output_dir=output_dir)
        config = EvaluationConfig(
            mode="patch_vote",
            runs_per_item=1,
            save_trajectories=False,
        )
        executor = ItemExecutor(
            llm_provider=provider,
            config=config,
            persistence=persistence,
        )

        item = _make_benchmark_item(truth_label=1)

        regions = [
            Region(x=idx * 10, y=idx * 10, width=224, height=224) for idx in range(30)
        ]
        reader = MagicMock()
        reader.__enter__ = MagicMock(return_value=reader)
        reader.__exit__ = MagicMock(return_value=None)
        reader.get_metadata.return_value = MagicMock(width=1000, height=1000)
        reader.get_thumbnail.return_value = Image.new("RGB", (64, 64), color="white")
        reader.read_region.side_effect = [
            Image.new("RGB", (224, 224), color="white") for _ in range(30)
        ]

        segmentor_instance = MagicMock()
        segmentor_instance.segment.return_value = object()

        with (
            patch("giant.wsi.reader.WSIReader", return_value=reader),
            patch("giant.vision.TissueSegmentor", return_value=segmentor_instance),
            patch("giant.vision.sample_patches", return_value=regions),
        ):
            result = await executor.run_single_item(item)

        assert provider.generate_response.await_count == 30
        assert result.prediction == "Lung"
        assert result.predicted_label == 1
        assert result.correct is True

    @pytest.mark.asyncio
    async def test_patch_vote_resamples_regions_per_run(self, tmp_path: Path) -> None:
        """Patch-vote baseline should resample patches across runs (BUG-046)."""
        provider = MagicMock()
        provider.get_model_name.return_value = "gpt-5.2"
        provider.get_provider_name.return_value = "openai"

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        persistence = ResultsPersistence(output_dir=output_dir)
        config = EvaluationConfig(
            mode="patch_vote",
            runs_per_item=2,
            save_trajectories=False,
        )
        executor = ItemExecutor(
            llm_provider=provider, config=config, persistence=persistence
        )

        item = _make_benchmark_item(truth_label=1)

        regions_a = [Region(x=idx, y=idx, width=224, height=224) for idx in range(30)]
        regions_b = [
            Region(x=10_000 + idx, y=10_000 + idx, width=224, height=224)
            for idx in range(30)
        ]

        reader = MagicMock()
        reader.__enter__ = MagicMock(return_value=reader)
        reader.__exit__ = MagicMock(return_value=None)
        reader.get_metadata.return_value = MagicMock(width=1000, height=1000)
        reader.get_thumbnail.return_value = MagicMock()

        segmentor_instance = MagicMock()
        segmentor_instance.segment.return_value = object()

        run_result = _make_run_result(answer="Lung", success=True)

        with (
            patch("giant.wsi.reader.WSIReader", return_value=reader),
            patch("giant.vision.TissueSegmentor", return_value=segmentor_instance),
            patch(
                "giant.vision.sample_patches",
                side_effect=[regions_a, regions_b],
            ) as mock_sample,
            patch(
                "giant.core.baselines.encode_image_to_base64",
                return_value=("b64", "image/jpeg"),
            ),
            patch(
                "giant.core.baselines.run_baseline_answer",
                new_callable=AsyncMock,
                return_value=run_result,
            ) as mock_run,
            patch("giant.eval.executor.extract_label", return_value=MagicMock(label=1)),
        ):
            result = await executor.run_single_item(item)

        assert mock_sample.call_count == 2
        assert [call.kwargs["seed"] for call in mock_sample.call_args_list] == [42, 43]
        assert mock_run.await_count == 60
        assert result.correct is True


class TestRunItemPatch:
    @pytest.mark.asyncio
    async def test_patch_resamples_regions_per_run(self, tmp_path: Path) -> None:
        """Patch baseline should resample patches across runs (BUG-046)."""
        provider = MagicMock()
        provider.get_model_name.return_value = "gpt-5.2"
        provider.get_provider_name.return_value = "openai"

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        persistence = ResultsPersistence(output_dir=output_dir)
        config = EvaluationConfig(
            mode="patch", runs_per_item=2, save_trajectories=False
        )
        executor = ItemExecutor(
            llm_provider=provider, config=config, persistence=persistence
        )

        item = _make_benchmark_item(truth_label=1)

        regions_a = [Region(x=idx, y=idx, width=224, height=224) for idx in range(30)]
        regions_b = [
            Region(x=10_000 + idx, y=10_000 + idx, width=224, height=224)
            for idx in range(30)
        ]

        reader = MagicMock()
        reader.__enter__ = MagicMock(return_value=reader)
        reader.__exit__ = MagicMock(return_value=None)
        reader.get_metadata.return_value = MagicMock(width=1000, height=1000)
        reader.get_thumbnail.return_value = MagicMock()

        segmentor_instance = MagicMock()
        segmentor_instance.segment.return_value = object()

        run_result = _make_run_result(answer="Lung", success=True)

        with (
            patch("giant.wsi.reader.WSIReader", return_value=reader),
            patch("giant.vision.TissueSegmentor", return_value=segmentor_instance),
            patch(
                "giant.vision.sample_patches",
                side_effect=[regions_a, regions_b],
            ) as mock_sample,
            patch("giant.core.baselines.make_patch_collage", return_value=object()),
            patch(
                "giant.core.baselines.encode_image_to_base64",
                return_value=("b64", "image/jpeg"),
            ),
            patch(
                "giant.core.baselines.run_baseline_answer",
                new_callable=AsyncMock,
                side_effect=[run_result, run_result],
            ),
            patch("giant.eval.executor.extract_label", return_value=MagicMock(label=1)),
        ):
            result = await executor.run_single_item(item)

        assert mock_sample.call_count == 2
        assert [call.kwargs["seed"] for call in mock_sample.call_args_list] == [42, 43]
        assert result.correct is True


class TestMajorityVote:
    """Tests for ItemExecutor._majority_vote method."""

    def test_returns_most_common(self) -> None:
        """Verify most common prediction wins."""
        result = ItemExecutor._majority_vote(["A", "B", "A", "A"])
        assert result == "A"

    def test_tiebreak_returns_first_most_common(self) -> None:
        """Verify tie returns first most common (Counter behavior)."""
        result = ItemExecutor._majority_vote(["A", "B"])
        # Counter.most_common returns first-seen on tie
        assert result in {"A", "B"}


class TestSelectMajorityPrediction:
    """Tests for ItemExecutor._select_majority_prediction method."""

    def test_single_prediction_passthrough(self) -> None:
        """Verify single prediction is returned as-is."""
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["Only"],
            labels=[42],
        )
        assert pred == "Only"
        assert label == 42

    def test_majority_label_wins(self) -> None:
        """Verify majority label determines winner."""
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["A", "B", "C"],
            labels=[1, 2, 2],
        )
        assert label == 2
        assert pred in {"B", "C"}

    def test_none_labels_excluded(self) -> None:
        """Verify None labels don't participate in voting."""
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["fail", "fail", "success"],
            labels=[None, None, 1],
        )
        assert label == 1
        assert pred == "success"

    def test_all_none_falls_back_to_string_vote(self) -> None:
        """Verify all-None labels fall back to string voting."""
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["foo", "bar", "bar"],
            labels=[None, None, None],
        )
        assert label is None
        assert pred == "bar"

    def test_raises_on_empty(self) -> None:
        """Verify empty predictions raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            ItemExecutor._select_majority_prediction(
                predictions=[],
                labels=[],
            )

    def test_raises_on_length_mismatch(self) -> None:
        """Verify mismatched lengths raise ValueError."""
        with pytest.raises(ValueError, match="must have the same length"):
            ItemExecutor._select_majority_prediction(
                predictions=["A", "B"],
                labels=[1],
            )
