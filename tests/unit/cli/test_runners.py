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
                model="claude-opus-4-5-20251101",
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
                model="claude-opus-4-5-20251101",
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
                model="claude-opus-4-5-20251101",
                max_steps=5,
                runs=10,  # Request 10 runs
                budget_usd=1.0,  # But budget is only $1
                verbose=0,
            )

            # Should stop after 2 runs ($1.00 total)
            assert result.total_cost <= 1.0
            assert mock_agent.run.call_count <= 2


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
