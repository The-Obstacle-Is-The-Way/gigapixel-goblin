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
    json_str = _extract_json_object(text)
    obj = json.loads(json_str)
    if not isinstance(obj, dict):
        return None

    if "isup_grade" not in obj:
        return None
    grade = obj["isup_grade"]
    if grade is None:
        return 0  # Benign/no cancer = ISUP Grade 0
    try:
        grade_int = int(grade)
    except (TypeError, ValueError):
        return None
    return grade_int if _ISUP_GRADE_MIN <= grade_int <= _ISUP_GRADE_MAX else None


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
        # C4 fix: Skip empty/whitespace options (empty string matches everything)
        if not opt.strip():
            continue
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

    # Normalize benchmark name for case-insensitive matching (C5 fix)
    benchmark_name_lower = benchmark_name.lower()

    # Special handling for PANDA: extract JSON isup_grade
    if benchmark_name_lower == "panda":
        try:
            label = _extract_panda_label(text)
            return ExtractedAnswer(label=label, raw=text)
        except (json.JSONDecodeError, ValueError):
            # C1 fix: Fall through to integer extraction instead of returning None
            label = None

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
    """Extract the first valid JSON object from text.

    Uses json.JSONDecoder().raw_decode() to find the first complete
    JSON object, ignoring any text before or after it.

    Args:
        text: Text potentially containing a JSON object.

    Returns:
        The extracted JSON string (reserialized for validity).

    Raises:
        ValueError: If no valid JSON object is found.
    """
    # Find first '{' to start scanning
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    # Use raw_decode to parse the first complete JSON object
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text, idx=start)
        if not isinstance(obj, dict):
            raise ValueError("Extracted JSON is not an object")
        # Reserialize to ensure valid JSON string
        return json.dumps(obj)
    except json.JSONDecodeError as e:
        raise ValueError(f"No valid JSON object found: {e}") from e
