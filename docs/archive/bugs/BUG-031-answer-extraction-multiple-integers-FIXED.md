# BUG-031: Answer Extraction Fails When Prediction Contains Multiple Integers

## Severity: P2 (Evaluation correctness / robustness)

## Status: Fixed

## Summary

For multiple-choice benchmarks, `extract_label()` previously used the **first** integer found in
`answer_text` to determine the selected option. If the prediction contained an out-of-range
integer before the real option index (e.g., level-0 coordinates like `15000`), extraction would
fail and incorrectly mark the item as an extraction failure.

## Root Cause

`src/giant/eval/answer_extraction.py` used:
- `_INT_RE.search(text)` → first integer only
- If that integer was out of range, it did **not** search for any subsequent integers.

## Fix

`src/giant/eval/answer_extraction.py` now iterates all integers in the prediction and selects
the **first** integer that is within `1..len(options)`.

## Verification

- Added regression test: `tests/unit/eval/test_answer_extraction.py` (`test_multiple_integers_prefers_first_in_range`).
