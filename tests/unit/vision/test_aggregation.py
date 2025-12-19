"""Tests for giant.vision.aggregation module (Spec-11)."""

from __future__ import annotations

import pytest

from giant.vision.aggregation import aggregate_predictions


class TestAggregatePredictions:
    """Tests for majority vote aggregation."""

    def test_unanimous_vote(self) -> None:
        """Test all predictions are the same."""
        predictions = ["Lung", "Lung", "Lung", "Lung"]
        assert aggregate_predictions(predictions) == "Lung"

    def test_clear_majority(self) -> None:
        """Test majority wins (3 vs 1 vs 1)."""
        predictions = ["Lung", "Breast", "Lung", "Lung", "Colon"]
        assert aggregate_predictions(predictions) == "Lung"

    def test_tie_breaks_alphabetically(self) -> None:
        """Test ties are broken alphabetically (deterministic)."""
        # Breast and Lung both have 2 votes
        predictions = ["Breast", "Lung", "Breast", "Lung"]
        # "Breast" comes before "Lung" alphabetically
        assert aggregate_predictions(predictions) == "Breast"

    def test_three_way_tie_alphabetical(self) -> None:
        """Test three-way tie breaks alphabetically."""
        predictions = ["Colon", "Lung", "Breast"]
        # "Breast" < "Colon" < "Lung" alphabetically
        assert aggregate_predictions(predictions) == "Breast"

    def test_single_prediction(self) -> None:
        """Test single prediction returns that prediction."""
        assert aggregate_predictions(["Heart"]) == "Heart"

    def test_empty_raises_value_error(self) -> None:
        """Test empty input raises ValueError."""
        with pytest.raises(ValueError, match="No predictions to aggregate"):
            aggregate_predictions([])

    def test_case_sensitive(self) -> None:
        """Test predictions are case-sensitive."""
        predictions = ["lung", "LUNG", "Lung"]
        # All different, tie-break alphabetical: "LUNG" < "Lung" < "lung" (ASCII order)
        assert aggregate_predictions(predictions) == "LUNG"

    def test_preserves_original_case(self) -> None:
        """Test that the winning prediction preserves its original case."""
        predictions = ["BREAST", "BREAST", "Lung"]
        assert aggregate_predictions(predictions) == "BREAST"

    def test_numeric_strings(self) -> None:
        """Test aggregation works with numeric string labels."""
        predictions = ["1", "2", "1", "1", "3"]
        assert aggregate_predictions(predictions) == "1"

    def test_tie_with_numbers_alphabetical(self) -> None:
        """Test numeric ties break lexicographically."""
        predictions = ["10", "2", "10", "2"]
        # "10" < "2" lexicographically (string comparison, not numeric)
        assert aggregate_predictions(predictions) == "10"
