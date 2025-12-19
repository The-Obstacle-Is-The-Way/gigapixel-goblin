"""Tests for giant.data.schemas module (Spec-10)."""

from __future__ import annotations

from giant.data.schemas import (
    BENCHMARK_TASKS,
    BenchmarkItem,
    BenchmarkResult,
)


class TestBenchmarkTasks:
    """Tests for BENCHMARK_TASKS constant."""

    def test_has_expected_benchmarks(self) -> None:
        """Test that all expected benchmark tasks are defined."""
        expected = {"tcga", "panda", "gtex", "tcga_expert_vqa", "tcga_slidebench"}
        assert set(BENCHMARK_TASKS.keys()) == expected

    def test_tcga_task_metadata(self) -> None:
        """Test TCGA task has correct metadata from paper."""
        tcga = BENCHMARK_TASKS["tcga"]
        assert tcga["questions"] == 221
        assert tcga["classes"] == 30
        assert tcga["metric"] == "balanced_accuracy"

    def test_panda_task_metadata(self) -> None:
        """Test PANDA task has correct metadata."""
        panda = BENCHMARK_TASKS["panda"]
        assert panda["questions"] == 197
        assert panda["classes"] == 6
        assert panda["metric"] == "balanced_accuracy"

    def test_gtex_task_metadata(self) -> None:
        """Test GTEx task has correct metadata."""
        gtex = BENCHMARK_TASKS["gtex"]
        assert gtex["questions"] == 191
        assert gtex["classes"] == 20
        assert gtex["metric"] == "balanced_accuracy"

    def test_vqa_tasks_use_accuracy(self) -> None:
        """Test VQA tasks use accuracy metric."""
        assert BENCHMARK_TASKS["tcga_expert_vqa"]["metric"] == "accuracy"
        assert BENCHMARK_TASKS["tcga_slidebench"]["metric"] == "accuracy"


class TestBenchmarkItem:
    """Tests for BenchmarkItem model."""

    def test_create_classification_item(self) -> None:
        """Test creating a classification benchmark item."""
        item = BenchmarkItem(
            benchmark_name="tcga",
            benchmark_id="TCGA-001",
            image_path="TCGA-001.svs",
            prompt="What type of cancer is shown?",
            options=["Lung adenocarcinoma", "Breast invasive carcinoma"],
            metric_type="balanced_accuracy",
            truth_label=1,
            wsi_path="/data/wsi/TCGA-001.svs",
        )
        assert item.benchmark_name == "tcga"
        assert item.truth_label == 1
        assert len(item.options) == 2

    def test_create_vqa_item_without_options(self) -> None:
        """Test creating a VQA item without options."""
        item = BenchmarkItem(
            benchmark_name="tcga_expert_vqa",
            benchmark_id="VQA-001",
            image_path="slide.svs",
            prompt="What is the depth of invasion?",
            options=None,
            metric_type="accuracy",
            truth_label=2,
            wsi_path="/data/wsi/slide.svs",
        )
        assert item.options is None
        assert item.metric_type == "accuracy"

    def test_panda_item_with_isup_grade(self) -> None:
        """Test PANDA item with ISUP grade truth label."""
        item = BenchmarkItem(
            benchmark_name="panda",
            benchmark_id="PANDA-001",
            image_path="panda_001.tiff",
            prompt="What is the ISUP grade?",
            options=["0", "1", "2", "3", "4", "5"],
            metric_type="balanced_accuracy",
            truth_label=3,  # ISUP grade 3
            wsi_path="/data/wsi/panda_001.tiff",
        )
        assert item.truth_label == 3


class TestBenchmarkResult:
    """Tests for BenchmarkResult model."""

    def test_create_correct_result(self) -> None:
        """Test creating a correct result."""
        result = BenchmarkResult(
            item_id="TCGA-001",
            prediction="The tissue shows lung adenocarcinoma",
            predicted_label=1,
            truth_label=1,
            correct=True,
            cost_usd=0.05,
            total_tokens=1500,
            trajectory_file="/results/TCGA-001.json",
        )
        assert result.correct is True
        assert result.predicted_label == result.truth_label

    def test_create_incorrect_result(self) -> None:
        """Test creating an incorrect result."""
        result = BenchmarkResult(
            item_id="TCGA-002",
            prediction="I think this is breast cancer",
            predicted_label=2,
            truth_label=1,
            correct=False,
            trajectory_file="/results/TCGA-002.json",
        )
        assert result.correct is False
        assert result.predicted_label != result.truth_label

    def test_result_with_error(self) -> None:
        """Test result with error (e.g., API failure)."""
        result = BenchmarkResult(
            item_id="TCGA-003",
            prediction="",
            predicted_label=None,
            truth_label=1,
            correct=False,
            trajectory_file="/results/TCGA-003.json",
            error="API timeout after 3 retries",
        )
        assert result.error is not None
        assert result.predicted_label is None

    def test_default_cost_and_tokens(self) -> None:
        """Test default values for cost and tokens."""
        result = BenchmarkResult(
            item_id="test",
            prediction="answer",
            truth_label=1,
            correct=True,
            trajectory_file="/test.json",
        )
        assert result.cost_usd == 0.0
        assert result.total_tokens == 0
