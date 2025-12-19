"""Tests for CLI runners (Spec-12)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from giant.cli.runners import (
    BenchmarkResult,
    InferenceResult,
    download_multipathqa,
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

    def test_default_values(self) -> None:
        result = BenchmarkResult(
            metrics={"accuracy": 0.5},
            total_cost=10.0,
        )
        assert result.n_items == 0
        assert result.n_errors == 0

    def test_with_counts(self) -> None:
        result = BenchmarkResult(
            metrics={"balanced_accuracy": 0.32},
            total_cost=50.0,
            n_items=100,
            n_errors=5,
        )
        assert result.n_items == 100
        assert result.n_errors == 5


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
            patch("giant.agent.GIANTAgent"),
            patch("giant.cli.runners.asyncio.run") as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.answer = "Test answer"
            mock_result.total_cost = 0.10
            mock_result.trajectory = MagicMock(turns=[])
            mock_run.return_value = mock_result

            result = run_single_inference(
                wsi_path=mock_wsi,
                question="What is this?",
                mode=Mode.giant,
                provider=Provider.anthropic,
                model="claude-sonnet-4-20250514",
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
            patch("giant.agent.GIANTAgent"),
            patch("giant.cli.runners.asyncio.run") as mock_run,
        ):
            # Simulate 3 runs with 2 agreeing answers
            mock_results = [
                MagicMock(
                    success=True,
                    answer="Cancer",
                    total_cost=0.10,
                    trajectory=MagicMock(turns=[]),
                ),
                MagicMock(
                    success=True,
                    answer="Normal",
                    total_cost=0.10,
                    trajectory=MagicMock(turns=[]),
                ),
                MagicMock(
                    success=True,
                    answer="Cancer",
                    total_cost=0.10,
                    trajectory=MagicMock(turns=[]),
                ),
            ]
            mock_run.side_effect = mock_results

            result = run_single_inference(
                wsi_path=mock_wsi,
                question="What?",
                mode=Mode.giant,
                provider=Provider.anthropic,
                model="claude-sonnet-4-20250514",
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
            patch("giant.agent.GIANTAgent"),
            patch("giant.cli.runners.asyncio.run") as mock_run,
        ):
            mock_result = MagicMock(
                success=True,
                answer="Test",
                total_cost=0.50,
                trajectory=MagicMock(turns=[]),
            )
            mock_run.return_value = mock_result

            result = run_single_inference(
                wsi_path=mock_wsi,
                question="What?",
                mode=Mode.giant,
                provider=Provider.anthropic,
                model="claude-sonnet-4-20250514",
                max_steps=5,
                runs=10,  # Request 10 runs
                budget_usd=1.0,  # But budget is only $1
                verbose=0,
            )

            # Should stop after 2 runs ($1.00 total)
            assert result.total_cost <= 1.0
            assert mock_run.call_count <= 2


class TestDownloadMultipathqa:
    """Tests for download_multipathqa function."""

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "new_dir"

        with patch("giant.cli.runners.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_response = MagicMock()
            mock_response.content = b"benchmark_name,question_id\ntcga,1\n"
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            success = download_multipathqa(
                dataset="multipathqa",
                output_dir=output_dir,
                verbose=0,
            )

            assert success is True
            assert output_dir.exists()
            assert (output_dir / "multipathqa" / "MultiPathQA.csv").exists()

    def test_handles_http_error(self, tmp_path: Path) -> None:
        import httpx

        with patch("giant.cli.runners.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.HTTPError("Connection failed")
            mock_client_class.return_value = mock_client

            success = download_multipathqa(
                dataset="multipathqa",
                output_dir=tmp_path,
                verbose=0,
            )

            assert success is False
