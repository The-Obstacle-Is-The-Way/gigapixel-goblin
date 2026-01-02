"""Tests for CLI runners (Spec-12)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from giant.cli.runners import (
    BenchmarkResult,
    InferenceResult,
    download_dataset,
    run_single_inference,
)
from giant.llm.model_registry import DEFAULT_ANTHROPIC_MODEL


class TestInferenceResult:
    """Tests for InferenceResult dataclass."""

    def test_default_values(self) -> None:
        result = InferenceResult(
            success=True,
            answer="Cancer",
            total_cost=0.50,
        )
        assert result.success is True
        assert result.answer == "Cancer"
        assert result.total_cost == 0.50
        assert result.total_tokens == 0
        assert result.trajectory is None
        assert result.error_message is None
        assert result.runs_answers == []
        assert result.agreement == 1.0

    def test_with_all_fields(self) -> None:
        result = InferenceResult(
            success=False,
            answer="Unknown",
            total_cost=1.0,
            trajectory={"turns": []},
            error_message="API error",
            runs_answers=["A", "B", "A"],
            agreement=0.67,
        )
        assert result.error_message == "API error"
        assert len(result.runs_answers) == 3


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_fields(self, tmp_path: Path) -> None:
        result = BenchmarkResult(
            run_id="run-001",
            results_path=tmp_path / "results.json",
            metrics={"accuracy": 0.5},
            total_cost=10.0,
            n_items=0,
            n_errors=0,
        )
        assert result.run_id == "run-001"
        assert result.n_items == 0
        assert result.n_errors == 0


class TestRunSingleInference:
    """Tests for run_single_inference function."""

    @pytest.fixture
    def mock_wsi(self, tmp_path: Path) -> Path:
        wsi = tmp_path / "test.svs"
        wsi.touch()
        return wsi

    def test_giant_mode_calls_agent(self, mock_wsi: Path) -> None:
        from giant.cli.main import Mode, Provider

        with (
            patch("giant.llm.create_provider") as mock_provider,
            patch("giant.agent.GIANTAgent") as mock_agent_cls,
        ):
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    answer="Test answer",
                    total_cost=0.10,
                    total_tokens=123,
                    error_message=None,
                    trajectory=MagicMock(turns=[]),
                )
            )
            mock_agent_cls.return_value = mock_agent

            result = run_single_inference(
                wsi_path=mock_wsi,
                question="What is this?",
                mode=Mode.giant,
                provider=Provider.anthropic,
                model=DEFAULT_ANTHROPIC_MODEL,
                max_steps=5,
                runs=1,
                budget_usd=0,
                verbose=0,
            )

            assert result.success is True
            assert result.answer == "Test answer"
            mock_provider.assert_called_once()

    def test_multiple_runs_majority_vote(self, mock_wsi: Path) -> None:
        from giant.cli.main import Mode, Provider

        with (
            patch("giant.llm.create_provider"),
            patch("giant.agent.GIANTAgent") as mock_agent_cls,
        ):
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(
                side_effect=[
                    MagicMock(
                        success=True,
                        answer="Cancer",
                        total_cost=0.10,
                        total_tokens=10,
                        error_message=None,
                        trajectory=MagicMock(turns=[]),
                    ),
                    MagicMock(
                        success=True,
                        answer="Normal",
                        total_cost=0.10,
                        total_tokens=10,
                        error_message=None,
                        trajectory=MagicMock(turns=[]),
                    ),
                    MagicMock(
                        success=True,
                        answer="Cancer",
                        total_cost=0.10,
                        total_tokens=10,
                        error_message=None,
                        trajectory=MagicMock(turns=[]),
                    ),
                ]
            )
            mock_agent_cls.return_value = mock_agent

            result = run_single_inference(
                wsi_path=mock_wsi,
                question="What?",
                mode=Mode.giant,
                provider=Provider.anthropic,
                model=DEFAULT_ANTHROPIC_MODEL,
                max_steps=5,
                runs=3,
                budget_usd=0,
                verbose=0,
            )

            # Should pick majority answer
            assert result.answer == "Cancer"
            assert result.agreement == 2 / 3
            assert result.total_cost == pytest.approx(0.30)

    def test_budget_stops_early(self, mock_wsi: Path) -> None:
        from giant.cli.main import Mode, Provider

        with (
            patch("giant.llm.create_provider"),
            patch("giant.agent.GIANTAgent") as mock_agent_cls,
        ):
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    answer="Test",
                    total_cost=0.50,
                    total_tokens=10,
                    error_message=None,
                    trajectory=MagicMock(turns=[]),
                )
            )
            mock_agent_cls.return_value = mock_agent

            result = run_single_inference(
                wsi_path=mock_wsi,
                question="What?",
                mode=Mode.giant,
                provider=Provider.anthropic,
                model=DEFAULT_ANTHROPIC_MODEL,
                max_steps=5,
                runs=10,  # Request 10 runs
                budget_usd=1.0,  # But budget is only $1
                verbose=0,
            )

            # Should stop after 2 runs ($1.00 total)
            assert result.total_cost <= 1.0
            assert mock_agent.run.call_count <= 2

    def test_patch_mode_resamples_patches_across_runs(self, mock_wsi: Path) -> None:
        from giant.cli.main import Mode, Provider

        reader = MagicMock()
        reader.__enter__ = MagicMock(return_value=reader)
        reader.__exit__ = MagicMock(return_value=None)
        reader.get_metadata.return_value = MagicMock(width=1000, height=1000)
        reader.get_thumbnail.return_value = MagicMock()
        reader.read_region.return_value = MagicMock()

        segmentor_instance = MagicMock()
        segmentor_instance.segment.return_value = object()

        region_a = MagicMock(x=0, y=0, width=224, height=224)
        region_b = MagicMock(x=10, y=10, width=224, height=224)

        baseline_result = MagicMock(
            success=True,
            answer="Cancer",
            total_cost=0.10,
            total_tokens=10,
            error_message=None,
            trajectory=MagicMock(turns=[]),
        )

        with (
            patch("giant.llm.create_provider", return_value=MagicMock()),
            patch("giant.wsi.WSIReader", return_value=reader),
            patch("giant.vision.TissueSegmentor", return_value=segmentor_instance),
            patch(
                "giant.vision.sample_patches",
                side_effect=[[region_a], [region_b]],
            ) as mock_sample,
            patch("giant.core.baselines.make_patch_collage", return_value=object()),
            patch(
                "giant.core.baselines.encode_image_to_base64",
                return_value=("b64", "image/jpeg"),
            ),
            patch(
                "giant.core.baselines.run_baseline_answer",
                new_callable=AsyncMock,
                side_effect=[baseline_result, baseline_result],
            ) as mock_baseline,
        ):
            run_single_inference(
                wsi_path=mock_wsi,
                question="What?",
                mode=Mode.patch,
                provider=Provider.openai,
                model="gpt-5.2",
                max_steps=5,
                runs=2,
                budget_usd=0,
                verbose=0,
            )

        assert mock_sample.call_count == 2
        assert [call.kwargs["seed"] for call in mock_sample.call_args_list] == [42, 43]
        # Patch mode runs baseline once per run (collage of all patches)
        assert mock_baseline.await_count == 2

    def test_patch_vote_resamples_patches_across_runs(self, mock_wsi: Path) -> None:
        from giant.cli.main import Mode, Provider

        reader = MagicMock()
        reader.__enter__ = MagicMock(return_value=reader)
        reader.__exit__ = MagicMock(return_value=None)
        reader.get_metadata.return_value = MagicMock(width=1000, height=1000)
        reader.get_thumbnail.return_value = MagicMock()
        reader.read_region.return_value = MagicMock()

        segmentor_instance = MagicMock()
        segmentor_instance.segment.return_value = object()

        region_a = MagicMock(x=0, y=0, width=224, height=224)
        region_b = MagicMock(x=10, y=10, width=224, height=224)

        baseline_patch = MagicMock(
            success=True,
            answer="Cancer",
            total_cost=0.01,
            total_tokens=1,
            error_message=None,
            trajectory=MagicMock(turns=[]),
        )

        with (
            patch("giant.llm.create_provider", return_value=MagicMock()),
            patch("giant.wsi.WSIReader", return_value=reader),
            patch("giant.vision.TissueSegmentor", return_value=segmentor_instance),
            patch(
                "giant.vision.sample_patches",
                side_effect=[[region_a], [region_b]],
            ) as mock_sample,
            patch(
                "giant.core.baselines.encode_image_to_base64",
                return_value=("b64", "image/jpeg"),
            ),
            patch(
                "giant.core.baselines.run_baseline_answer",
                new_callable=AsyncMock,
                return_value=baseline_patch,
            ) as mock_run,
        ):
            run_single_inference(
                wsi_path=mock_wsi,
                question="What?",
                mode=Mode.patch_vote,
                provider=Provider.openai,
                model="gpt-5.2",
                max_steps=5,
                runs=2,
                budget_usd=0,
                verbose=0,
            )

        assert mock_sample.call_count == 2
        assert [call.kwargs["seed"] for call in mock_sample.call_args_list] == [42, 43]
        assert mock_run.await_count == 2


class TestDownloadDataset:
    """Tests for download_dataset function."""

    def test_downloads_multipathqa_metadata(self, tmp_path: Path) -> None:
        expected_path = tmp_path / "multipathqa" / "MultiPathQA.csv"
        with patch(
            "giant.data.download.download_multipathqa_metadata",
            return_value=expected_path,
        ) as mock_dl:
            result = download_dataset(
                dataset="multipathqa",
                output_dir=tmp_path,
                force=False,
                verbose=0,
            )

        assert result["dataset"] == "multipathqa"
        assert result["path"] == str(expected_path)
        mock_dl.assert_called_once_with(tmp_path / "multipathqa", force=False)

    def test_rejects_unknown_dataset(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown dataset"):
            download_dataset(
                dataset="tcga",
                output_dir=tmp_path,
                force=False,
                verbose=0,
            )
