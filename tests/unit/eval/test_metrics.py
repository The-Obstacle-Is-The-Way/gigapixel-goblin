"""Tests for giant.eval.metrics module (Spec-10)."""

from __future__ import annotations

import pytest

from giant.eval.metrics import (
    BootstrapResult,
    accuracy,
    balanced_accuracy,
    bootstrap_metric,
)


class TestAccuracy:
    """Tests for accuracy metric."""

    def test_perfect_accuracy(self) -> None:
        """Test 100% accuracy."""
        predictions = [1, 2, 3, 4, 5]
        truths = [1, 2, 3, 4, 5]
        assert accuracy(predictions, truths) == 1.0

    def test_zero_accuracy(self) -> None:
        """Test 0% accuracy."""
        predictions = [1, 1, 1, 1, 1]
        truths = [2, 2, 2, 2, 2]
        assert accuracy(predictions, truths) == 0.0

    def test_partial_accuracy(self) -> None:
        """Test partial accuracy."""
        predictions = [1, 2, 1, 2, 1]
        truths = [1, 2, 3, 4, 5]
        assert accuracy(predictions, truths) == 0.4  # 2/5

    def test_empty_input_raises(self) -> None:
        """Test that empty input raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            accuracy([], [])


class TestBalancedAccuracy:
    """Tests for balanced accuracy metric."""

    def test_perfect_balanced_accuracy(self) -> None:
        """Test perfect balanced accuracy."""
        predictions = [1, 1, 2, 2, 3, 3]
        truths = [1, 1, 2, 2, 3, 3]
        assert balanced_accuracy(predictions, truths) == 1.0

    def test_imbalanced_but_perfect(self) -> None:
        """Test perfect accuracy on imbalanced data."""
        # Class 1: 4 samples, Class 2: 1 sample
        predictions = [1, 1, 1, 1, 2]
        truths = [1, 1, 1, 1, 2]
        assert balanced_accuracy(predictions, truths) == 1.0

    def test_biased_classifier_penalized(self) -> None:
        """Test that biased classifier gets lower balanced accuracy."""
        # Classifier always predicts class 1
        predictions = [1, 1, 1, 1, 1]
        truths = [1, 1, 1, 1, 2]
        # Regular accuracy: 4/5 = 0.8
        assert accuracy(predictions, truths) == 0.8
        # Balanced accuracy: (1.0 + 0.0) / 2 = 0.5
        assert balanced_accuracy(predictions, truths) == 0.5

    def test_two_class_balanced(self) -> None:
        """Test balanced accuracy with two classes."""
        # Class 1: 3 correct out of 4 (75%)
        # Class 2: 1 correct out of 2 (50%)
        predictions = [1, 1, 1, 2, 1, 2]
        truths = [1, 1, 1, 1, 2, 2]
        # Balanced: (3/4 + 1/2) / 2 = (0.75 + 0.5) / 2 = 0.625
        assert balanced_accuracy(predictions, truths) == pytest.approx(0.625)

    def test_empty_input_raises(self) -> None:
        """Test that empty input raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            balanced_accuracy([], [])


class TestBootstrapResult:
    """Tests for BootstrapResult model."""

    def test_bootstrap_result_attributes(self) -> None:
        """Test BootstrapResult has all expected attributes."""
        result = BootstrapResult(
            mean=0.75,
            std=0.05,
            ci_lower=0.65,
            ci_upper=0.85,
            n_replicates=1000,
        )
        assert result.mean == 0.75
        assert result.std == 0.05
        assert result.ci_lower == 0.65
        assert result.ci_upper == 0.85
        assert result.n_replicates == 1000


class TestBootstrapMetric:
    """Tests for bootstrap_metric function."""

    def test_perfect_predictions_low_variance(self) -> None:
        """Test bootstrap on perfect predictions has low variance."""
        predictions = [1, 2, 3, 4, 5] * 20  # 100 items
        truths = [1, 2, 3, 4, 5] * 20
        result = bootstrap_metric(predictions, truths, accuracy, n_replicates=100)
        assert result.mean == pytest.approx(1.0)
        assert result.std < 0.01

    def test_deterministic_with_seed(self) -> None:
        """Test bootstrap is deterministic with same seed."""
        predictions = [1, 2, 1, 2, 1, 2] * 10
        truths = [1, 2, 2, 1, 1, 2] * 10
        result1 = bootstrap_metric(predictions, truths, accuracy, seed=42)
        result2 = bootstrap_metric(predictions, truths, accuracy, seed=42)
        assert result1.mean == result2.mean
        assert result1.std == result2.std

    def test_different_seeds_different_results(self) -> None:
        """Test different seeds give (slightly) different results."""
        predictions = [1, 2, 1, 2, 1, 2] * 10
        truths = [1, 2, 2, 1, 1, 2] * 10
        result1 = bootstrap_metric(predictions, truths, accuracy, seed=42)
        result2 = bootstrap_metric(predictions, truths, accuracy, seed=123)
        # Mean should be close but std may differ slightly
        assert result1.std != result2.std

    def test_confidence_interval_contains_mean(self) -> None:
        """Test that CI contains the mean."""
        predictions = [1, 2, 1, 2, 1] * 20
        truths = [1, 2, 2, 1, 1] * 20
        result = bootstrap_metric(predictions, truths, accuracy)
        assert result.ci_lower <= result.mean <= result.ci_upper

    def test_default_replicates_is_1000(self) -> None:
        """Test default number of bootstrap replicates is 1000."""
        predictions = [1, 2, 3]
        truths = [1, 2, 3]
        result = bootstrap_metric(predictions, truths, accuracy)
        assert result.n_replicates == 1000

    def test_custom_replicates(self) -> None:
        """Test custom number of replicates."""
        predictions = [1, 2, 3]
        truths = [1, 2, 3]
        result = bootstrap_metric(predictions, truths, accuracy, n_replicates=500)
        assert result.n_replicates == 500

    def test_with_balanced_accuracy(self) -> None:
        """Test bootstrap with balanced accuracy metric."""
        # Imbalanced: 8 class-1, 2 class-2
        predictions = [1, 1, 1, 1, 1, 1, 1, 1, 2, 2]
        truths = [1, 1, 1, 1, 1, 1, 1, 1, 2, 2]
        result = bootstrap_metric(predictions, truths, balanced_accuracy)
        assert result.mean == pytest.approx(1.0, abs=0.05)
