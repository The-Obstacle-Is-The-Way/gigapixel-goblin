# BUG-046: Patch Baselines Reuse the Same Sampled Patches Across `runs_per_item`

**Date**: 2026-01-02
**Severity**: FUTURE (P4) — evaluation-quality / cost-efficiency issue
**Status**: ✅ FIXED (2026-01-02)
**Discovered by**: Adversarial audit during benchmark hardening

## Summary

In `patch` and `patch_vote` evaluation modes, patch regions were sampled **once per item** (with a deterministic default seed), then reused for all `runs_per_item`. Increasing `runs_per_item` therefore did **not** increase patch diversity; it only repeated LLM calls on the same patch images.

This can:
- waste money when `runs_per_item > 1`,
- and make “majority vote across runs” less meaningful for patch baselines.

## Locations

- `src/giant/eval/executor.py` (`patch`, `patch_vote` item execution)
- `src/giant/cli/runners.py` (`patch`, `patch_vote` single-slide baselines)
- Deterministic default seed:
  - `src/giant/vision/sampler.py:20-26` (`seed: int = 42`)

## The Behavior (Evidence)

### `patch` mode

The code samples patches and builds a single montage once:

```python
# src/giant/eval/executor.py
regions = sample_patches(...)
patch_images = [reader.read_region(...) for r in regions]
collage = make_patch_collage(patch_images, patch_size=PATCH_SIZE)
request = BaselineRequest(image_base64=encode(collage), ...)
```

Then reuses `request` for each run:

```python
for run_idx in range(self.config.runs_per_item):
    run_result = await run_baseline_answer(..., request=request)
```

### `patch_vote` mode

`_prepare_patch_vote_requests()` samples once and returns `patch_requests` (one per patch), and `_run_item_patch_vote()` reuses the same `patch_requests` for each run:

```python
regions, patch_requests = self._prepare_patch_vote_requests(item)
for run_idx in range(self.config.runs_per_item):
    await self._run_patch_vote_single_run(..., patch_requests=patch_requests)
```

`sample_patches()` is called without an explicit seed, so it uses the default `seed=42`.

## Impact

This is not a correctness bug for default settings (`runs_per_item=1`), but it is a real evaluation-quality issue:

- If a user sets `runs_per_item > 1` expecting “independent runs”, patch baselines do not get new patches.
- Additional runs mostly measure LLM stochasticity rather than patch-sampling variance.

## Fix

Implemented by resampling patches per run using `seed=42 + run_idx` and rebuilding
baseline requests per run for both `patch` and `patch_vote`.

## Tests to Add

- Unit test ensuring that with `runs_per_item=2`, patch regions differ between runs when using different seeds (e.g., seed=42 vs seed=43), and that patch-vote runs produce different region sets when configured.

## Acceptance Criteria

- When `runs_per_item > 1`, patch baseline runs sample different patch sets by default (or provide an explicit config flag controlling this).
- Default behavior for `runs_per_item=1` remains unchanged.
