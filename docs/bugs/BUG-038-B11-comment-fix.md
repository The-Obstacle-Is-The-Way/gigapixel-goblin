# BUG-038-B11: Misleading Comment on Step Index

**Status**: IMPROVEMENT (cosmetic fix)
**Severity**: LOW
**Component**: `src/giant/agent/context.py`
**Lines**: 268
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

A comment in `_apply_image_pruning()` says `user_msg_index` is `(== step-1)`. This is easy to misread because the codebase uses multiple “step” concepts (LLM call step number vs `Turn.step_index` in the trajectory).

This is a cosmetic clarity fix: make the comment explicit about what “step” means here.

---

## Current Code

**File**: `src/giant/agent/context.py:267-268`

```python
pruned_messages: list[Message] = []
user_msg_index = 0  # 0-based index among user messages (== step-1)
```

---

## Problem Analysis

### Why It's Misleading

- `user_msg_index` counts **user messages** in the prompt history built for the next LLM call.
- The `(== step-1)` mapping is plausible, but ambiguous without stating which step numbering is meant.

### Actual Meaning

- `user_msg_index = 0` → thumbnail prompt (LLM step 1)
- `user_msg_index = 1` → prompt containing the first crop image (LLM step 2)
- `user_msg_index = 2` → prompt containing the second crop image (LLM step 3)
- etc.

---

## Impact Assessment

### Direct Impact

- **None**: Code behavior is correct
- **Maintenance risk**: Future developer might misunderstand the logic

### Risk Level

- **VERY LOW**: Cosmetic fix only

---

## Fix Implementation

### Update Comment

```python
pruned_messages: list[Message] = []
user_msg_index = 0  # 0-based index among user messages (0 = thumbnail prompt; 1+ = crop prompts)
```

---

## Verification

No tests needed - this is a comment-only change.

```bash
# Just verify linting passes
uv run ruff check src/giant/agent/context.py
```

---

## Dependencies

- **Blocked by**: None
- **Blocks**: None
- **Related**: None

---

## Sign-Off Checklist

- [ ] Comment updated
- [ ] Lint passes (`uv run ruff check .`)
- [ ] PR created (can be combined with other B11/B12 fixes)
