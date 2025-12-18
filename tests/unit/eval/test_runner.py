"""Tests for giant.eval.runner module (Spec-10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from giant.data.schemas import BenchmarkResult
from giant.eval.runner import BenchmarkRunner


class _DummyProvider:
    def get_model_name(self) -> str:
        return "gpt-5.2"


@pytest.fixture
def runner(tmp_path: Path) -> BenchmarkRunner:
    return BenchmarkRunner(
        llm_provider=_DummyProvider(),  # type: ignore[arg-type]
        wsi_root=tmp_path / "wsi",
        output_dir=tmp_path / "out",
    )


class TestResolveWsiPath:
    def test_rejects_absolute_path(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="absolute paths are not allowed"):
            runner._resolve_wsi_path("/etc/passwd", "tcga")

    def test_rejects_path_traversal(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="path traversal"):
            runner._resolve_wsi_path("../secret.svs", "tcga")

    def test_finds_direct_path(self, runner: BenchmarkRunner) -> None:
        runner.wsi_root.mkdir(parents=True)
        (runner.wsi_root / "slide.svs").write_text("not a real slide")
        resolved = runner._resolve_wsi_path("slide.svs", "tcga")
        assert resolved == runner.wsi_root / "slide.svs"

    def test_finds_benchmark_subdir_path(self, runner: BenchmarkRunner) -> None:
        (runner.wsi_root / "tcga").mkdir(parents=True)
        (runner.wsi_root / "tcga" / "slide.svs").write_text("not a real slide")
        resolved = runner._resolve_wsi_path("slide.svs", "tcga")
        assert resolved == runner.wsi_root / "tcga" / "slide.svs"


class TestTruthLabelParsing:
    def test_parses_integer_label(self, runner: BenchmarkRunner) -> None:
        assert runner._parse_truth_label(" 2 ", "tcga", None) == 2

    def test_parses_string_label_case_insensitive(
        self, runner: BenchmarkRunner
    ) -> None:
        assert runner._parse_truth_label("LiVeR", "gtex", ["heart", "liver"]) == 2

    def test_rejects_empty_label(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="Empty truth label"):
            runner._parse_truth_label("  ", "tcga", None)

    def test_rejects_unparseable_label(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="Could not parse truth label"):
            runner._parse_truth_label("???", "tcga", None)


class TestMajorityVote:
    def test_votes_on_labels_when_available(self, runner: BenchmarkRunner) -> None:
        pred, label = runner._select_majority_prediction(
            predictions=["A", "1", "B"],
            labels=[1, 1, 2],
        )
        assert label == 1
        assert pred in {"A", "1"}

    def test_falls_back_to_string_vote_when_all_labels_none(
        self, runner: BenchmarkRunner
    ) -> None:
        pred, label = runner._select_majority_prediction(
            predictions=["foo", "bar", "bar"],
            labels=[None, None, None],
        )
        assert label is None
        assert pred == "bar"


class TestComputeMetrics:
    def test_errors_count_as_incorrect(self, runner: BenchmarkRunner) -> None:
        results = [
            BenchmarkResult(
                item_id="1",
                prediction="1",
                predicted_label=1,
                truth_label=1,
                correct=True,
                trajectory_file="",
            ),
            BenchmarkResult(
                item_id="2",
                prediction="",
                predicted_label=None,
                truth_label=2,
                correct=False,
                trajectory_file="",
                error="boom",
            ),
        ]

        metrics = runner._compute_metrics(results, benchmark_name="tcga_slidebench")
        assert metrics["point_estimate"] == 0.5
        assert metrics["n_total"] == 2
        assert metrics["n_errors"] == 1
        assert metrics["n_extraction_failures"] == 0

    def test_extraction_failures_count_as_incorrect(
        self, runner: BenchmarkRunner
    ) -> None:
        results = [
            BenchmarkResult(
                item_id="1",
                prediction="1",
                predicted_label=1,
                truth_label=1,
                correct=True,
                trajectory_file="",
            ),
            BenchmarkResult(
                item_id="2",
                prediction="unparseable",
                predicted_label=None,
                truth_label=2,
                correct=False,
                trajectory_file="",
                error=None,
            ),
        ]

        metrics = runner._compute_metrics(results, benchmark_name="tcga_slidebench")
        assert metrics["point_estimate"] == 0.5
        assert metrics["n_total"] == 2
        assert metrics["n_errors"] == 0
        assert metrics["n_extraction_failures"] == 1
