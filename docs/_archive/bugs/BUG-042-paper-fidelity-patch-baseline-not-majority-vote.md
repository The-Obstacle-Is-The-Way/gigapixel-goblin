# BUG-042: Paper-Fidelity Gap — Patch Baseline Is a Collage, Not Per-Patch Majority Vote

## Severity: P2 (Medium) — Baseline Comparability / Paper Reproducibility

## Status: ✅ Fixed (2026-01-01)

## Resolution

Added an explicit paper-fidelity baseline mode:

- Eval/CLI mode: `patch_vote`
- Behavior: samples 30 patches and runs 30 independent baseline calls, then aggregates via majority vote
- Preserved: existing `patch` mode remains the collage/montage baseline for quick comparisons

## Summary

The GIANT paper’s “patch baseline” is defined as **30 independent patch evaluations aggregated by majority vote**.

Our current “patch” mode does something materially different:
- Samples 30 patches (good),
- Builds a **single montage/collage image** of those patches,
- Runs the LMM **once** on the collage (not 30 times),
- Therefore cannot be compared to the paper’s reported patch baseline numbers.

---

## Paper Requirement (Source of Truth)

The paper’s baseline definition:

- “We sample 30 random 224×224 patches … The model independently answers each patch, and predictions are combined by majority vote.” (`_literature/markdown/giant/giant.md:184`)

---

## Current Implementation (What We Do Today)

`src/giant/eval/executor.py:_run_item_patch`:

1. Samples `N_PATCHES` patch regions and reads them (`src/giant/eval/executor.py:227-242`).
2. Creates a collage: `collage = make_patch_collage(patch_images, patch_size=PATCH_SIZE)` (`src/giant/eval/executor.py:243`).
3. Sends a single request with the collage, explicitly described as a montage (`src/giant/eval/executor.py:250-253`).
4. Calls `run_baseline_answer(...)` once per run (`src/giant/eval/executor.py:263-267`).

This is aligned with `src/giant/core/baselines.py`’s stated behavior (“Patch baseline (montage of random patches, answer-only)”).

---

## Impact

- Any “patch baseline” results produced by this repo are **not directly comparable** to the paper’s patch baseline.
- Depending on model behavior, the collage baseline could be:
  - stronger (model can integrate across patches in one view), or
  - weaker/confusing (small patches in a grid, reduced effective resolution).
- This can mislead “GIANT vs patch baseline” claims and complicate reproduction audits.

---

## Implemented Fix (Paper-Faithful Patch Baseline Mode)

Implemented `mode="patch_vote"` in evaluation and CLI:

1. Sample 30 tissue patches (same sampler/segmentor path as the collage baseline).
2. For each patch, run `run_baseline_answer(...)` with the single patch image.
3. Aggregate the 30 patch predictions via majority vote to produce one prediction per item/run.
4. Preserve `mode="patch"` as the existing montage/collage baseline.

---

## Test Plan

Unit tests with a fake provider (no live calls):

1. **Calls provider 30× per item**
   - Ensure patch-vote mode triggers 30 `generate_response` calls for one benchmark item.

2. **Majority vote aggregation**
   - Provide deterministic per-patch answers and assert final aggregated label is correct (including tie behavior).

---

## Acceptance Criteria

- A new paper-faithful patch baseline mode exists that matches `_literature/markdown/giant/giant.md:184`.
- Documentation clearly distinguishes collage vs per-patch-vote baselines.
- Benchmarks can be rerun with paper-faithful baselines for apples-to-apples comparisons.
