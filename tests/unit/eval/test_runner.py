"""Tests for giant.eval.runner module (Spec-10)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from giant.data.schemas import BenchmarkResult
from giant.eval.executor import ItemExecutor
from giant.eval.loader import BenchmarkItemLoader
from giant.eval.persistence import ResultsPersistence
from giant.eval.runner import BenchmarkRunner, EvaluationConfig


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


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    """Create a test CSV file."""
    csv_file = tmp_path / "test.csv"
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "benchmark_name",
                "benchmark_id",
                "image_path",
                "prompt",
                "options",
                "answer",
                "is_valid",
                "file_id",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "benchmark_name": "tcga",
                "benchmark_id": "TCGA-001",
                "image_path": "slide1.svs",
                "prompt": "What is this?",
                "options": json.dumps(["Lung", "Breast", "Colon"]),
                "answer": "1",
                "is_valid": "True",
                "file_id": "uuid-1",
            }
        )
        writer.writerow(
            {
                "benchmark_name": "tcga",
                "benchmark_id": "TCGA-002",
                "image_path": "slide2.svs",
                "prompt": "Choose: {options}",
                "options": "Lung|Breast",
                "answer": "Lung",
                "is_valid": "True",
                "file_id": "uuid-2",
            }
        )
        # Invalid row (filtered out)
        writer.writerow(
            {
                "benchmark_name": "tcga",
                "benchmark_id": "TCGA-003",
                "image_path": "slide3.svs",
                "prompt": "Invalid",
                "options": "",
                "answer": "1",
                "is_valid": "False",
                "file_id": "uuid-3",
            }
        )
        # Different benchmark (filtered out)
        writer.writerow(
            {
                "benchmark_name": "panda",
                "benchmark_id": "PANDA-001",
                "image_path": "panda.svs",
                "prompt": "Grade?",
                "options": "",
                "answer": "2",
                "is_valid": "True",
                "file_id": "panda-1",
            }
        )
    return csv_file


class TestEvaluationConfigValidation:
    def test_budget_requires_single_worker(self) -> None:
        with pytest.raises(ValueError, match="budget_usd"):
            EvaluationConfig(max_concurrent=2, budget_usd=1.0)


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

    def test_tcga_alias_benchmarks_resolve_under_tcga_dir(
        self, runner: BenchmarkRunner
    ) -> None:
        (runner.wsi_root / "tcga").mkdir(parents=True)
        (runner.wsi_root / "tcga" / "slide.svs").write_text("not a real slide")
        resolved = runner._resolve_wsi_path("slide.svs", "tcga_expert_vqa")
        assert resolved == runner.wsi_root / "tcga" / "slide.svs"

    def test_finds_gdc_client_file_id_dir(self, runner: BenchmarkRunner) -> None:
        file_id = "uuid-123"
        (runner.wsi_root / "tcga" / file_id).mkdir(parents=True)
        downloaded = runner.wsi_root / "tcga" / file_id / "slide.something.svs"
        downloaded.write_text("not a real slide")
        resolved = runner._resolve_wsi_path("slide.svs", "tcga", file_id=file_id)
        assert resolved == downloaded

    def test_resolves_dicom_directory_single_series(
        self, runner: BenchmarkRunner
    ) -> None:
        """DICOM directory resolution should require a single SeriesInstanceUID."""
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid

        dicom_dir = runner.wsi_root / "gtex" / "GTEX-TEST"
        dicom_dir.mkdir(parents=True, exist_ok=True)

        series_uid = generate_uid()

        def write_dicom(path: Path) -> None:
            file_meta = FileMetaDataset()
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            file_meta.MediaStorageSOPClassUID = generate_uid()
            file_meta.MediaStorageSOPInstanceUID = generate_uid()
            file_meta.ImplementationClassUID = generate_uid()

            ds = Dataset()
            ds.file_meta = file_meta
            ds.SeriesInstanceUID = series_uid
            ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
            ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
            ds.save_as(path, enforce_file_format=True)

        write_dicom(dicom_dir / "a.dcm")
        write_dicom(dicom_dir / "b.dcm")

        resolved = runner._resolve_wsi_path("GTEX-TEST.tiff", "gtex")
        assert resolved.parent == dicom_dir
        assert resolved.suffix == ".dcm"

    def test_resolves_dicom_directory_multiple_series_raises(
        self, runner: BenchmarkRunner
    ) -> None:
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid

        dicom_dir = runner.wsi_root / "gtex" / "GTEX-MULTI"
        dicom_dir.mkdir(parents=True, exist_ok=True)

        def write_dicom(path: Path, *, series_uid: str) -> None:
            file_meta = FileMetaDataset()
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            file_meta.MediaStorageSOPClassUID = generate_uid()
            file_meta.MediaStorageSOPInstanceUID = generate_uid()
            file_meta.ImplementationClassUID = generate_uid()

            ds = Dataset()
            ds.file_meta = file_meta
            ds.SeriesInstanceUID = series_uid
            ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
            ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
            ds.save_as(path, enforce_file_format=True)

        write_dicom(dicom_dir / "a.dcm", series_uid=generate_uid())
        write_dicom(dicom_dir / "b.dcm", series_uid=generate_uid())

        with pytest.raises(ValueError, match="multiple DICOM series"):
            runner._resolve_wsi_path("GTEX-MULTI.tiff", "gtex")


class TestTruthLabelParsing:
    def test_parses_integer_label(self, runner: BenchmarkRunner) -> None:
        assert BenchmarkItemLoader.parse_truth_label(" 2 ", "tcga", None) == 2

    def test_rejects_zero_label_with_options(self, runner: BenchmarkRunner) -> None:
        """Truth labels for multiple-choice tasks are 1-based."""
        with pytest.raises(ValueError, match="out of range"):
            BenchmarkItemLoader.parse_truth_label("0", "tcga", ["A", "B"])

    def test_rejects_out_of_range_label_with_options(
        self, runner: BenchmarkRunner
    ) -> None:
        with pytest.raises(ValueError, match="out of range"):
            BenchmarkItemLoader.parse_truth_label("3", "tcga", ["A", "B"])

    def test_rejects_out_of_range_panda_grade(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="ISUP"):
            BenchmarkItemLoader.parse_truth_label("6", "panda", None)

    def test_parses_string_label_case_insensitive(
        self, runner: BenchmarkRunner
    ) -> None:
        assert (
            BenchmarkItemLoader.parse_truth_label("LiVeR", "gtex", ["heart", "liver"])
            == 2
        )

    def test_rejects_empty_label(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="Empty truth label"):
            BenchmarkItemLoader.parse_truth_label("  ", "tcga", None)

    def test_rejects_unparseable_label(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="Could not parse truth label"):
            BenchmarkItemLoader.parse_truth_label("???", "tcga", None)


class TestMajorityVote:
    def test_votes_on_labels_when_available(self, runner: BenchmarkRunner) -> None:
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["A", "1", "B"],
            labels=[1, 1, 2],
        )
        assert label == 1
        assert pred in {"A", "1"}

    def test_falls_back_to_string_vote_when_all_labels_none(
        self, runner: BenchmarkRunner
    ) -> None:
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["foo", "bar", "bar"],
            labels=[None, None, None],
        )
        assert label is None
        assert pred == "bar"

    def test_none_labels_excluded_from_voting(self, runner: BenchmarkRunner) -> None:
        """Verify that None labels don't participate in voting.

        This is a regression test for P2-9: when some runs fail to parse labels
        (returning None), those None values should not affect the vote count.
        Previously, None could tie with valid labels and win due to first-seen
        tie-breaking.
        """
        # Scenario: 2 None labels, 2 valid labels with value 1
        # Before fix: None and 1 tie, None wins because it appears first
        # After fix: Only valid labels counted, 1 wins
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["failed", "answer_1", "failed2", "answer_1b"],
            labels=[None, 1, None, 1],
        )
        assert label == 1
        assert pred in {"answer_1", "answer_1b"}

    def test_single_valid_label_wins_over_many_nones(
        self, runner: BenchmarkRunner
    ) -> None:
        """Even one valid label should win over any number of Nones."""
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["failed", "failed", "failed", "success"],
            labels=[None, None, None, 5],
        )
        assert label == 5
        assert pred == "success"


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

    def test_empty_results_returns_error(self, runner: BenchmarkRunner) -> None:
        metrics = runner._compute_metrics([], benchmark_name="tcga")
        assert "error" in metrics
        assert metrics["error"] == "No results to compute metrics"


class TestLoadBenchmarkItems:
    def test_loads_items_from_csv(
        self, runner: BenchmarkRunner, csv_path: Path, tmp_path: Path
    ) -> None:
        # Create WSI files
        wsi_root = tmp_path / "wsi"
        wsi_root.mkdir()
        (wsi_root / "slide1.svs").write_text("slide1")
        (wsi_root / "slide2.svs").write_text("slide2")

        items = runner.load_benchmark_items(csv_path, "tcga")

        assert len(items) == 2
        assert items[0].benchmark_id == "TCGA-001"
        assert items[0].truth_label == 1
        assert items[0].options == ["Lung", "Breast", "Colon"]
        assert items[0].file_id == "uuid-1"
        assert items[1].benchmark_id == "TCGA-002"
        assert items[1].truth_label == 1  # "Lung" matches first option
        assert "1. Lung" in items[1].prompt  # {options} was substituted
        assert items[1].file_id == "uuid-2"

    def test_is_valid_with_trailing_whitespace_is_respected(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "valid-whitespace.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_name",
                    "benchmark_id",
                    "image_path",
                    "prompt",
                    "options",
                    "answer",
                    "is_valid",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_name": "tcga",
                    "benchmark_id": "TCGA-WS",
                    "image_path": "slide.svs",
                    "prompt": "Q?",
                    "options": json.dumps(["A", "B"]),
                    "answer": "1",
                    "is_valid": "True ",
                }
            )

        runner.wsi_root.mkdir(parents=True, exist_ok=True)
        (runner.wsi_root / "slide.svs").write_text("slide")

        items = runner.load_benchmark_items(csv_file, "tcga")
        assert [i.benchmark_id for i in items] == ["TCGA-WS"]

    def test_parses_python_literal_options(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "literal.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_name",
                    "benchmark_id",
                    "image_path",
                    "prompt",
                    "options",
                    "answer",
                    "is_valid",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_name": "tcga",
                    "benchmark_id": "TCGA-LITERAL",
                    "image_path": "literal.svs",
                    "prompt": "Choose: {options}",
                    "options": "['Lung', 'Breast', 'Colon']",
                    "answer": "2",
                    "is_valid": "True",
                }
            )

        (runner.wsi_root / "literal.svs").parent.mkdir(parents=True, exist_ok=True)
        (runner.wsi_root / "literal.svs").write_text("slide")

        items = runner.load_benchmark_items(csv_file, "tcga")
        assert len(items) == 1
        assert items[0].options == ["Lung", "Breast", "Colon"]
        assert "1. Lung" in items[0].prompt

    def test_appends_options_when_placeholder_missing(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "vqa.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_name",
                    "benchmark_id",
                    "image_path",
                    "prompt",
                    "options",
                    "answer",
                    "is_valid",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_name": "tcga_expert_vqa",
                    "benchmark_id": "Q-001",
                    "image_path": "slide.svs",
                    "prompt": "What is the level of mitotic activity?",
                    "options": "['Low', 'Medium', 'High', 'Cannot determine']",
                    "answer": "1",
                    "is_valid": "True",
                }
            )

        (runner.wsi_root / "tcga").mkdir(parents=True)
        (runner.wsi_root / "tcga" / "slide.svs").write_text("slide")

        items = runner.load_benchmark_items(csv_file, "tcga_expert_vqa")
        assert len(items) == 1
        assert "Select from the following options" in items[0].prompt
        assert "1. Low" in items[0].prompt
        assert "Please respond with the option number" in items[0].prompt

    def test_loads_duplicate_image_paths_with_unique_benchmark_ids(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "expert.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_name",
                    "benchmark_id",
                    "image_path",
                    "prompt",
                    "options",
                    "answer",
                    "is_valid",
                    "file_id",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_name": "tcga_expert_vqa",
                    "benchmark_id": "Q-001",
                    "image_path": "same_slide.svs",
                    "prompt": "Q1?",
                    "options": json.dumps(["A", "B"]),
                    "answer": "1",
                    "is_valid": "True",
                    "file_id": "uuid-same",
                }
            )
            writer.writerow(
                {
                    "benchmark_name": "tcga_expert_vqa",
                    "benchmark_id": "Q-002",
                    "image_path": "same_slide.svs",
                    "prompt": "Q2?",
                    "options": json.dumps(["A", "B"]),
                    "answer": "2",
                    "is_valid": "True",
                    "file_id": "uuid-same",
                }
            )

        (runner.wsi_root / "tcga").mkdir(parents=True)
        (runner.wsi_root / "tcga" / "same_slide.svs").write_text("slide")

        items = runner.load_benchmark_items(csv_file, "tcga_expert_vqa")
        assert [i.benchmark_id for i in items] == ["Q-001", "Q-002"]
        expected = str(runner.wsi_root / "tcga" / "same_slide.svs")
        assert all(i.wsi_path == expected for i in items)

    def test_raises_on_missing_csv(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(FileNotFoundError, match="MultiPathQA CSV not found"):
            runner.load_benchmark_items(Path("/nonexistent/file.csv"), "tcga")

    def test_raises_on_unknown_benchmark(
        self, runner: BenchmarkRunner, csv_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="Unknown benchmark"):
            runner.load_benchmark_items(csv_path, "nonexistent_benchmark")

    def test_raises_on_invalid_truth_label(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "bad.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_name",
                    "benchmark_id",
                    "image_path",
                    "prompt",
                    "options",
                    "answer",
                    "is_valid",
                    "file_id",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_name": "tcga",
                    "benchmark_id": "BAD-001",
                    "image_path": "bad.svs",
                    "prompt": "Q?",
                    "options": "",
                    "answer": "",  # Empty answer
                    "is_valid": "True",
                    "file_id": "uuid-bad",
                }
            )

        # Create the WSI file
        wsi_root = tmp_path / "wsi"
        wsi_root.mkdir()
        (wsi_root / "bad.svs").write_text("bad")

        with pytest.raises(ValueError, match="Invalid truth label"):
            runner.load_benchmark_items(csv_file, "tcga")

    def test_skips_missing_wsis_when_enabled(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "missing.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_name",
                    "benchmark_id",
                    "image_path",
                    "prompt",
                    "options",
                    "answer",
                    "is_valid",
                    "file_id",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_name": "tcga",
                    "benchmark_id": "HAS-WSI",
                    "image_path": "present.svs",
                    "prompt": "Q?",
                    "options": json.dumps(["A", "B"]),
                    "answer": "1",
                    "is_valid": "True",
                    "file_id": "uuid-present",
                }
            )
            writer.writerow(
                {
                    "benchmark_name": "tcga",
                    "benchmark_id": "MISSING-WSI",
                    "image_path": "missing.svs",
                    "prompt": "Q?",
                    "options": json.dumps(["A", "B"]),
                    "answer": "1",
                    "is_valid": "True",
                    "file_id": "uuid-missing",
                }
            )

        runner.wsi_root.mkdir(parents=True)
        (runner.wsi_root / "present.svs").write_text("present")

        items = runner.load_benchmark_items(csv_file, "tcga", skip_missing_wsis=True)
        assert [i.benchmark_id for i in items] == ["HAS-WSI"]

    def test_empty_options_list_is_treated_as_no_options(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "empty-options.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_name",
                    "benchmark_id",
                    "image_path",
                    "prompt",
                    "options",
                    "answer",
                    "is_valid",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_name": "tcga",
                    "benchmark_id": "EMPTY-OPTIONS",
                    "image_path": "slide.svs",
                    "prompt": "Q?",
                    "options": "[]",
                    "answer": "1",
                    "is_valid": "True",
                }
            )

        runner.wsi_root.mkdir(parents=True)
        (runner.wsi_root / "slide.svs").write_text("slide")

        items = runner.load_benchmark_items(csv_file, "tcga")
        assert len(items) == 1
        assert items[0].options is None

    def test_raises_on_missing_required_csv_columns(
        self, runner: BenchmarkRunner, tmp_path: Path
    ) -> None:
        csv_file = tmp_path / "missing-cols.csv"
        with csv_file.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "benchmark_id",
                    "prompt",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark_id": "MISSING-COLS",
                    "prompt": "Q?",
                }
            )

        with pytest.raises(ValueError, match=r"Missing required CSV columns"):
            runner.load_benchmark_items(csv_file, "tcga")


class TestValidateRunId:
    def test_rejects_absolute_path_run_id(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="Invalid run_id"):
            ResultsPersistence.validate_run_id("/etc/passwd")

    def test_rejects_path_traversal_run_id(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="Invalid run_id"):
            ResultsPersistence.validate_run_id("../escape")

    def test_rejects_subdir_run_id(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="Invalid run_id"):
            ResultsPersistence.validate_run_id("subdir/runid")

    def test_accepts_valid_run_id(self, runner: BenchmarkRunner) -> None:
        # Should not raise
        ResultsPersistence.validate_run_id("valid-run-id_2024")


class TestSafeFilenameComponent:
    def test_sanitizes_special_chars(self, runner: BenchmarkRunner) -> None:
        result = ResultsPersistence.safe_filename_component("item/with:special*chars")
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result

    def test_preserves_safe_chars(self, runner: BenchmarkRunner) -> None:
        result = ResultsPersistence.safe_filename_component("item_123.test-run")
        assert result == "item_123.test-run"


class TestWsiNotFound:
    def test_raises_on_missing_wsi(self, runner: BenchmarkRunner) -> None:
        runner.wsi_root.mkdir(parents=True)
        with pytest.raises(FileNotFoundError, match="WSI not found"):
            runner._resolve_wsi_path("nonexistent.svs", "tcga")


class TestSelectMajorityPrediction:
    def test_raises_on_length_mismatch(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="must have the same length"):
            ItemExecutor._select_majority_prediction(
                predictions=["a", "b"],
                labels=[1],
            )

    def test_raises_on_empty_predictions(self, runner: BenchmarkRunner) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            ItemExecutor._select_majority_prediction(
                predictions=[],
                labels=[],
            )

    def test_single_prediction_returns_as_is(self, runner: BenchmarkRunner) -> None:
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["only one"],
            labels=[42],
        )
        assert pred == "only one"
        assert label == 42

    def test_deterministic_tiebreak(self, runner: BenchmarkRunner) -> None:
        # Labels 1 and 2 each appear once - tie
        pred, label = ItemExecutor._select_majority_prediction(
            predictions=["first", "second"],
            labels=[1, 2],
        )
        # Should return the first one seen (deterministic)
        assert label == 1
        assert pred == "first"


class TestEvaluationConfig:
    def test_default_config(self) -> None:
        config = EvaluationConfig()
        assert config.max_steps == 20
        assert config.runs_per_item == 1
        assert config.max_concurrent == 4
        assert config.max_items is None
        assert config.skip_missing_wsis is False
        assert config.checkpoint_interval == 10

    def test_custom_config(self) -> None:
        config = EvaluationConfig(
            max_steps=50,
            runs_per_item=5,
            max_concurrent=2,
            max_items=10,
            skip_missing_wsis=True,
            checkpoint_interval=5,
        )
        assert config.max_steps == 50
        assert config.runs_per_item == 5
