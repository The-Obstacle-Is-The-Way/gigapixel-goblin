# Fix BUG-038-B7 (Retry Counter) & B11 (Docs)

## Summary
Completes the final items from the BUG-038 Comprehensive Audit.

### 🐛 Fixed Bugs
- **B7 (Medium):** Fixed logic error in `runner.py` where `_consecutive_errors` was not reset after a successful recovery from an invalid crop region. This prevented the agent from using its full retry budget in subsequent steps if a previous step had triggered a recovery.
  - Added reproduction test case `test_invalid_coordinates_recovery_resets_error_counter`.
- **B11 (Low):** Clarified confusing comment in `context.py` regarding `user_msg_index` to distinguish between LLM conversation steps and trajectory steps.

### ⏭️ Skipped
- **B9 (Refactor):** Decided to skip the iterative refactor of the recursive retry logic as the current recursion is bounded by `max_retries` and safe. This avoids unnecessary code churn.

## Verification
- **New Test:** `test_invalid_coordinates_recovery_resets_error_counter` passes.
- **Regression:** All 826 unit tests passed.
- **Lint/Type:** `ruff` and `mypy` checks passed (including E501 fix).
