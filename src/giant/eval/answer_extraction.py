"""Dataset-aware answer extraction for benchmark evaluation (Spec-10).

Implements answer extraction logic that canonicalizes model predictions
into integer labels for scoring. Handles the heterogeneous formats in
MultiPathQA:

- Multiple-choice tasks: 1-based option indices, letter (A-D), or text match
- PANDA: ISUP grade 0-5 from JSON object with "isup_grade" field
- GTEx: String label to option index mapping

Paper Reference: MultiPathQA truth labels are heterogeneous across benchmarks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# Regex patterns for extracting answers
_INT_RE = re.compile(r"\b(\d+)\b")
_LETTER_RE = re.compile(r"\b([A-D])\b", re.IGNORECASE)

# Number of options required for letter extraction (A-D mapping)
_LETTER_OPTION_COUNT = 4

# ISUP grade range for PANDA (0 = benign, 1-5 = cancer grades)
_ISUP_GRADE_MIN = 0
_ISUP_GRADE_MAX = 5


@dataclass(frozen=True)
class ExtractedAnswer:
    """Result of answer extraction.

    Attributes:
        label: Canonicalized integer label (None if extraction failed).
        raw: Original raw prediction text.
    """

    label: int | None
    raw: str


def _extract_panda_label(text: str) -> int | None:
    """Extract ISUP grade from PANDA JSON response.

    Handles:
    - {"isup_grade": 0-5} -> returns integer (validated to 0..5)
    - {"isup_grade": null} -> returns 0 (benign/no cancer)
    - missing "isup_grade" key -> returns None (extraction failure)
    """
    try:
        json_str = _extract_json_object(text)
        obj = json.loads(json_str)
        if "isup_grade" not in obj:
            return None
        grade = obj["isup_grade"]
        if grade is None:
            return 0  # Benign/no cancer = ISUP Grade 0
        grade_int = int(grade)
        return grade_int if _ISUP_GRADE_MIN <= grade_int <= _ISUP_GRADE_MAX else None
    except Exception:
        return None


def _has_isup_grade_key(text: str) -> bool:
    """Check if text contains a JSON object with 'isup_grade' key.

    Used to prevent fallback to naive integer extraction when PANDA JSON
    was found but had an invalid grade (out of range or type error).
    """
    try:
        json_str = _extract_json_object(text)
        obj = json.loads(json_str)
        return "isup_grade" in obj
    except Exception:
        return False


def _extract_from_options(text: str, options: list[str]) -> int | None:
    """Extract label from text when options are provided."""
    # Letter extraction (only for 4-option questions)
    if len(options) == _LETTER_OPTION_COUNT:
        m = _LETTER_RE.search(text)
        if m:
            letter = m.group(1).upper()
            return ord(letter) - ord("A") + 1  # A=1, B=2, C=3, D=4

    # Integer extraction (1-based): prefer the first integer that is in-range.
    for m in _INT_RE.finditer(text):
        k = int(m.group(1))
        if 1 <= k <= len(options):
            return k

    # Option text match (case-insensitive, longest-first to avoid false positives)
    lowered = text.lower()
    # Sort by length descending to match "heart" before "art"
    sorted_options = sorted(
        enumerate(options, start=1), key=lambda x: len(x[1]), reverse=True
    )
    for i, opt in sorted_options:
        if opt.lower() in lowered:
            return i

    return None


def _extract_integer(text: str) -> int | None:
    """Extract any integer from text."""
    m = _INT_RE.search(text)
    return int(m.group(1)) if m else None


def extract_label(
    prediction: str,
    *,
    benchmark_name: str,
    options: list[str] | None,
) -> ExtractedAnswer:
    """Extract a canonical integer label from model prediction.

    Conventions (from MultiPathQA CSV):
    - Multiple-choice tasks use 1-based labels.
    - PANDA uses isup_grade 0-5.
    - GTEx: answer is a string label; options list contains organ names.

    Args:
        prediction: Raw prediction text from the model.
        benchmark_name: Task name (tcga, panda, gtex, etc.).
        options: Answer options for multiple-choice (None for open-ended).

    Returns:
        ExtractedAnswer with canonicalized label and raw text.
    """
    text = prediction.strip()
    label: int | None = None

    # Special handling for PANDA: extract JSON isup_grade
    if benchmark_name == "panda":
        label = _extract_panda_label(text)
        # If PANDA JSON extraction returned a result, use it (don't fall back)
        # If it returned None but JSON with isup_grade was present, don't fall back
        # to integer extraction (which would grab coordinate numbers or invalid grades)
        if label is not None or _has_isup_grade_key(text):
            return ExtractedAnswer(label=label, raw=text)

    # If options exist, try letter (A-D), 1..N integer, or option text match
    if label is None and options:
        label = _extract_from_options(text, options)
        # Options exist but no match found - return early with None
        return ExtractedAnswer(label=label, raw=text)

    # No options: try integer extraction (fallback for non-PANDA or malformed PANDA)
    if label is None:
        label = _extract_integer(text)

    return ExtractedAnswer(label=label, raw=text)


def _extract_json_object(text: str) -> str:
    """Extract the outermost JSON object from text.

    Args:
        text: Text potentially containing a JSON object.

    Returns:
        The extracted JSON string.

    Raises:
        ValueError: If no JSON object is found.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return text[start : end + 1]
