"""Majority vote aggregation for patch-level predictions (Spec-11).

Paper Reference: "The model independently answers each patch, and
predictions are combined by majority vote."
"""

from __future__ import annotations

from collections import Counter


def aggregate_predictions(predictions: list[str]) -> str:
    """Majority vote with deterministic tie-breaking (alphabetical).

    Aggregates multiple patch-level predictions into a single slide-level
    prediction using majority voting. In case of ties, the lexicographically
    smallest prediction wins (deterministic).

    Args:
        predictions: List of string predictions from individual patches.

    Returns:
        The winning prediction string.

    Raises:
        ValueError: If predictions list is empty.
    """
    if not predictions:
        raise ValueError("No predictions to aggregate")

    counts = Counter(predictions)
    max_count = max(counts.values())

    # All predictions with max count (handle ties)
    winners = [pred for pred, count in counts.items() if count == max_count]

    # Deterministic tie-break: alphabetical (lexicographic) order
    return sorted(winners)[0]
