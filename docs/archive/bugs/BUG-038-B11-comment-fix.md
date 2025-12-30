# BUG-038-B11: Clarify `user_msg_index` Comment in Context Pruning

**Status**: FIXED (2025-12-29)
**Severity**: LOW
**Component**: `src/giant/agent/context.py`
**Fixed In**: `b5a57f59` (docs: BUG-038-B11 clarify user_msg_index comment)
**Buggy Commit**: `2c9f120e` (fix(agent): feed crop images into next step)
**Current Lines (fixed)**: `context.py:268-269`
**Buggy Lines (pre-fix)**: `context.py:268`
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

`ContextManager._apply_image_pruning()` uses `user_msg_index` as a 0-based index over **user messages**, where:

- index `0` is the initial thumbnail prompt (LLM step 1)
- index `1+` correspond to subsequent crop prompts (LLM step 2+)

Pre-fix, the inline comment implied `user_msg_index == step - 1` without clarifying what “step” meant, which is easy to misread because GIANT uses multiple step concepts (`Turn.step_index`, LLM step number, etc).

This was a comment-only clarity fix (no behavior change).

---

## Original Comment (pre-fix)

**File (pre-fix)**: `src/giant/agent/context.py:268` (commit `2c9f120e`)

```python
user_msg_index = 0  # 0-based index among user messages (== step-1)
```

---

## Current Comment (fixed)

**File (fixed)**: `src/giant/agent/context.py:268-269` (commit `b5a57f59`)

```python
# 0-based index among user messages (0 = thumbnail prompt; 1+ = crop prompts)
user_msg_index = 0
```

---

## Verification

No tests required (comment-only change).

```bash
uv run ruff check src/giant/agent/context.py
```
