"""Evaluation and benchmarking framework for GIANT (Spec-10).

This module provides tools to:
- Load MultiPathQA benchmark items
- Run the GIANT agent in batch mode
- Extract and canonicalize answers
- Calculate metrics (Accuracy, Balanced Accuracy)
- Compute bootstrap uncertainty estimates
- Save results with full provenance
"""

from giant.eval.answer_extraction import ExtractedAnswer, extract_label
from giant.eval.metrics import (
    BootstrapResult,
    accuracy,
    balanced_accuracy,
    bootstrap_metric,
)

__all__ = [
    "BootstrapResult",
    "ExtractedAnswer",
    "accuracy",
    "balanced_accuracy",
    "bootstrap_metric",
    "extract_label",
]
