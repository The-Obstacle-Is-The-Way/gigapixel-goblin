# BUG-021: Prompt Template Edge Case for `max_steps=1` (Not Reproducible)

## Severity: P4 (Claim inaccurate)

## Status: Closed (Not reproducible in current implementation)

## Description
The raw `INITIAL_USER_PROMPT` template includes a step-range instruction:

> “For Steps 1..{max_steps − 1} you MUST use `crop`.”

If someone rendered that template directly with `max_steps=1`, it would read “Steps 1..0”, which is nonsensical.

However, the runtime prompt construction uses `PromptBuilder`, which selects the final-step wording whenever `step == max_steps`. For `max_steps=1`, the very first message uses the final-step prompt (“You MUST use `answer` now”), so the “Steps 1..0” text is never produced.

## Evidence
- `src/giant/prompts/builder.py`: `_build_prompt_text()` checks `if step == max_steps` before the “initial step” branch.
- `src/giant/agent/context.py`: uses `PromptBuilder` for all message construction.

## Resolution
No code change required. Spec-07 documents the `max_steps=1` edge case to prevent future confusion.
