"""Tests for giant.eval.persistence module (Spec-10).

These tests verify the ResultsPersistence class that handles
saving evaluation artifacts to the filesystem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from giant.agent.runner import RunResult
from giant.agent.trajectory import Trajectory
from giant.eval.persistence import ResultsPersistence
from giant.eval.runner import EvaluationConfig, EvaluationResults


def _make_trajectory(
    *,
    wsi_path: str = "/path/to/slide.svs",
    question: str = "What is this?",
    final_answer: str | None = "Lung",
) -> Trajectory:
    """Create a Trajectory for testing."""
    return Trajectory(
        wsi_path=wsi_path,
        question=question,
        turns=[],
        final_answer=final_answer,
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
    trajectory = _make_trajectory(final_answer=answer if success else None)
    return RunResult(
        answer=answer,
        trajectory=trajectory,
        total_tokens=total_tokens,
        total_cost=total_cost,
        success=success,
        error_message=error_message,
    )


@pytest.fixture
def persistence(tmp_path: Path) -> ResultsPersistence:
    """Create a ResultsPersistence instance with a temp output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return ResultsPersistence(output_dir=output_dir)


class TestValidateRunId:
    """Tests for ResultsPersistence.validate_run_id method."""

    def test_accepts_valid_run_id(self) -> None:
        """Verify valid run IDs pass validation."""
        ResultsPersistence.validate_run_id("valid-run-id_2024")
        ResultsPersistence.validate_run_id("tcga_20240101_120000")
        ResultsPersistence.validate_run_id("test.run.id")

    def test_rejects_absolute_path(self) -> None:
        """Verify absolute paths are rejected."""
        with pytest.raises(ValueError, match="Invalid run_id"):
            ResultsPersistence.validate_run_id("/etc/passwd")

    def test_rejects_path_traversal(self) -> None:
        """Verify path traversal is rejected."""
        with pytest.raises(ValueError, match="Invalid run_id"):
            ResultsPersistence.validate_run_id("../escape")
        with pytest.raises(ValueError, match="Invalid run_id"):
            ResultsPersistence.validate_run_id("foo/../bar")

    def test_rejects_subdirectory(self) -> None:
        """Verify subdirectory paths are rejected."""
        with pytest.raises(ValueError, match="Invalid run_id"):
            ResultsPersistence.validate_run_id("subdir/runid")


class TestSafeFilenameComponent:
    """Tests for ResultsPersistence.safe_filename_component method."""

    def test_sanitizes_special_chars(self) -> None:
        """Verify special characters are replaced with underscores."""
        result = ResultsPersistence.safe_filename_component("item/with:special*chars")
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result
        assert "_" in result

    def test_preserves_safe_chars(self) -> None:
        """Verify safe characters are preserved."""
        result = ResultsPersistence.safe_filename_component("item_123.test-run")
        assert result == "item_123.test-run"

    def test_strips_leading_trailing_unsafe_chars(self) -> None:
        """Verify leading/trailing dots, underscores, dashes are stripped."""
        result = ResultsPersistence.safe_filename_component("._-item-_.")
        assert result == "item"

    def test_empty_string_returns_item(self) -> None:
        """Verify empty string returns 'item' as fallback."""
        result = ResultsPersistence.safe_filename_component("")
        assert result == "item"

    def test_all_unsafe_returns_item(self) -> None:
        """Verify all-unsafe input returns 'item' as fallback."""
        result = ResultsPersistence.safe_filename_component("///")
        assert result == "item"


class TestSaveTrajectory:
    """Tests for ResultsPersistence.save_trajectory method."""

    def test_saves_trajectory_json(self, persistence: ResultsPersistence) -> None:
        """Verify trajectory is saved as JSON file."""
        run_result = _make_run_result()

        path_str = persistence.save_trajectory(
            run_result=run_result,
            item_id="TCGA-001",
            run_idx=0,
        )

        path = Path(path_str)
        assert path.exists()
        assert path.suffix == ".json"
        assert "TCGA-001" in path.name
        assert "run0" in path.name

        # Verify content is valid JSON
        content = json.loads(path.read_text())
        assert "wsi_path" in content
        assert "question" in content

    def test_creates_trajectories_subdirectory(
        self, persistence: ResultsPersistence
    ) -> None:
        """Verify trajectories subdirectory is created."""
        run_result = _make_run_result()

        path_str = persistence.save_trajectory(
            run_result=run_result,
            item_id="TEST-001",
            run_idx=0,
        )

        path = Path(path_str)
        assert path.parent.name == "trajectories"
        assert path.parent.exists()

    def test_sanitizes_item_id_in_filename(
        self, persistence: ResultsPersistence
    ) -> None:
        """Verify item IDs with special chars are sanitized in filenames."""
        run_result = _make_run_result()

        path_str = persistence.save_trajectory(
            run_result=run_result,
            item_id="item/with:special*chars",
            run_idx=0,
        )

        path = Path(path_str)
        assert "/" not in path.name
        assert ":" not in path.name
        assert "*" not in path.name

    def test_multiple_runs_have_different_filenames(
        self, persistence: ResultsPersistence
    ) -> None:
        """Verify different run indices produce different filenames."""
        run_result = _make_run_result()

        path0 = persistence.save_trajectory(
            run_result=run_result,
            item_id="TEST-001",
            run_idx=0,
        )
        path1 = persistence.save_trajectory(
            run_result=run_result,
            item_id="TEST-001",
            run_idx=1,
        )

        assert path0 != path1
        assert "run0" in path0
        assert "run1" in path1


class TestSaveResults:
    """Tests for ResultsPersistence.save_results method."""

    def test_saves_results_json(self, persistence: ResultsPersistence) -> None:
        """Verify evaluation results are saved as JSON file."""
        results = EvaluationResults(
            run_id="test-run-001",
            benchmark_name="tcga",
            model_name="gpt-5.2",
            config=EvaluationConfig(),
            results=[],
            metrics={"accuracy": 0.85},
            total_cost_usd=1.23,
            total_tokens=10000,
            timestamp="2024-01-01T00:00:00Z",
        )

        path = persistence.save_results(results)

        assert path.exists()
        assert path.suffix == ".json"
        assert "test-run-001" in path.name
        assert "_results.json" in path.name

        # Verify content is valid JSON with expected fields
        content = json.loads(path.read_text())
        assert content["run_id"] == "test-run-001"
        assert content["benchmark_name"] == "tcga"
        assert content["model_name"] == "gpt-5.2"
        assert content["metrics"]["accuracy"] == 0.85

    def test_returns_path_object(self, persistence: ResultsPersistence) -> None:
        """Verify return value is a Path object."""
        results = EvaluationResults(
            run_id="test-run",
            benchmark_name="tcga",
            model_name="gpt-5.2",
            config=EvaluationConfig(),
            results=[],
        )

        path = persistence.save_results(results)

        assert isinstance(path, Path)


class TestResultsPersistenceIsFrozen:
    """Tests for ResultsPersistence immutability."""

    def test_is_frozen(self, persistence: ResultsPersistence) -> None:
        """Verify ResultsPersistence is frozen (immutable)."""
        with pytest.raises(AttributeError):
            persistence.output_dir = Path("/other")  # type: ignore[misc]
