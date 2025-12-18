"""Metrics for benchmark evaluation (Spec-10).

Implements:
- Accuracy: simple percentage correct
- Balanced Accuracy: macro-averaged per-class recall
- Bootstrap evaluation with mean ± std (paper reporting format)

Paper Reference: Table 1 reports "value ± std" from 1000 bootstrap replicates.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


def accuracy(predictions: list[int], truths: list[int]) -> float:
    """Calculate simple accuracy (percentage correct).

    Args:
        predictions: List of predicted labels.
        truths: List of ground truth labels.

    Returns:
        Accuracy as a float between 0 and 1.

    Raises:
        ValueError: If inputs are empty.
    """
    if not predictions or not truths:
        raise ValueError("Inputs must not be empty")

    correct = sum(p == t for p, t in zip(predictions, truths, strict=True))
    return correct / len(predictions)


def balanced_accuracy(predictions: list[int], truths: list[int]) -> float:
    """Calculate balanced accuracy (macro-averaged per-class recall).

    Balanced accuracy addresses class imbalance by averaging recall across
    all classes, giving equal weight to each class regardless of sample count.

    Formula: (1/K) * Σ_k (correct_k / total_k) for each class k

    Args:
        predictions: List of predicted labels.
        truths: List of ground truth labels.

    Returns:
        Balanced accuracy as a float between 0 and 1.

    Raises:
        ValueError: If inputs are empty.
    """
    if not predictions or not truths:
        raise ValueError("Inputs must not be empty")

    # Count samples per class
    class_counts: Counter[int] = Counter(truths)

    # Count correct predictions per class
    class_correct: Counter[int] = Counter()
    for pred, truth in zip(predictions, truths, strict=True):
        if pred == truth:
            class_correct[truth] += 1

    # Calculate per-class recall and average
    recalls = []
    for cls, count in class_counts.items():
        recall = class_correct[cls] / count
        recalls.append(recall)

    return sum(recalls) / len(recalls)


@dataclass(frozen=True)
class BootstrapResult:
    """Result of bootstrap evaluation.

    Paper Reference: Table 1 reports metrics as "value ± std" from 1000 bootstrap
    replicates. The primary output format is mean ± std; CI is optional for
    internal analysis.

    Attributes:
        mean: Bootstrap mean of the metric.
        std: Bootstrap standard deviation.
        ci_lower: 2.5th percentile (lower bound of 95% CI).
        ci_upper: 97.5th percentile (upper bound of 95% CI).
        n_replicates: Number of bootstrap replicates used.
    """

    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    n_replicates: int = 1000


def bootstrap_metric(
    predictions: list[int],
    truths: list[int],
    metric_fn: Callable[[list[int], list[int]], float],
    n_replicates: int = 1000,
    seed: int = 42,
) -> BootstrapResult:
    """Compute bootstrap estimate of a metric with uncertainty.

    Paper Reference: Algorithm from Section 4 - report mean ± std from B=1000
    bootstrap replicates for paper-faithful reporting.

    Algorithm:
    1. Input: List of (prediction, truth) pairs of length N.
    2. Repeat B times:
       - Sample N pairs with replacement.
       - Calculate the metric.
    3. Report bootstrap mean and standard deviation.
    4. (Optional) Compute 95% percentile interval.

    Args:
        predictions: List of predicted labels.
        truths: List of ground truth labels.
        metric_fn: Metric function (e.g., accuracy, balanced_accuracy).
        n_replicates: Number of bootstrap samples (default: 1000).
        seed: Random seed for reproducibility.

    Returns:
        BootstrapResult with mean, std, and confidence interval.
    """
    rng = np.random.default_rng(seed)
    n = len(predictions)

    scores = []
    for _ in range(n_replicates):
        idx = rng.choice(n, size=n, replace=True)
        sample_pred = [predictions[i] for i in idx]
        sample_truth = [truths[i] for i in idx]
        scores.append(metric_fn(sample_pred, sample_truth))

    scores_arr = np.array(scores)

    return BootstrapResult(
        mean=float(np.mean(scores_arr)),
        std=float(np.std(scores_arr, ddof=1)),
        ci_lower=float(np.percentile(scores_arr, 2.5)),
        ci_upper=float(np.percentile(scores_arr, 97.5)),
        n_replicates=n_replicates,
    )
