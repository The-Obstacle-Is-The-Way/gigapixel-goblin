# BUG-047: “Paper Parameter” Settings Exist but Are Not Wired Into Runtime

**Date**: 2026-01-02
**Severity**: FUTURE (P4) — configuration drift / reproducibility footgun
**Status**: ✅ FIXED (2026-01-02)
**Discovered by**: Adversarial audit during benchmark hardening

## Summary

`src/giant/config.py` defines several “Paper Parameters” and baseline settings (e.g., `MAX_ITERATIONS`, `OVERSAMPLING_BIAS`, `PATCH_COUNT`) that imply environment-variable control. Previously, these fields were not referenced by the runtime path that performs cropping, navigation, patch sampling, or metric bootstrapping.

Net effect (pre-fix): setting these environment variables did **not** change behavior, which could mislead users attempting reproduction or ablations.

## Fix

Implemented wiring so these Settings affect runtime defaults:

- `MAX_ITERATIONS`: default `max_steps` for `AgentConfig` and `EvaluationConfig`
- `THUMBNAIL_SIZE`: default `AgentConfig.thumbnail_size`
- `OVERSAMPLING_BIAS`: passed into `CropEngine.crop(..., bias=...)` in the agent
- `PATCH_COUNT` / `PATCH_SIZE`: used by patch baselines (CLI + evaluator)
- `BOOTSTRAP_REPLICATES`: used via `EvaluationConfig.bootstrap_replicates` → `bootstrap_metric(..., n_replicates=...)`
- `WSI_LONG_SIDE_TARGET`: acts as a paper-parameter alias for provider image sizes when `IMAGE_SIZE_OPENAI` / `IMAGE_SIZE_ANTHROPIC` are not explicitly set

## Locations (Settings Definitions)

`src/giant/config.py:67-85` defines:

- `WSI_LONG_SIDE_TARGET` (S)
- `MAX_ITERATIONS` (T)
- `OVERSAMPLING_BIAS`
- `THUMBNAIL_SIZE`
- `PATCH_SIZE` / `PATCH_COUNT`
- `BOOTSTRAP_REPLICATES`

## Evidence of Non-Wiring (Concrete Runtime Defaults)

### Navigation step limit (T)

- Agent config default is hard-coded: `src/giant/agent/runner.py:153` (`max_steps: int = 20`)

### Crop target size and oversampling bias (S, bias)

- Crop pipeline defaults are hard-coded parameters, not read from `settings`:
  - `src/giant/core/crop_engine.py:122-127` (`target_size: int = 1000`, `bias: float = 0.85`)

### Patch baselines (patch count/size)

- Patch size/count are constants, not `settings`:
  - `src/giant/vision/constants.py:9-12` (`N_PATCHES: int = 30`, `PATCH_SIZE: int = 224`)

### Bootstrap replicates

- Bootstrapping defaults to 1000 in code, not `settings`:
  - `src/giant/eval/metrics.py:102-108` (`n_replicates: int = 1000`)

## Impact

- Users may believe they are running with modified paper parameters via env vars, but runs remain unchanged.
- Reproducibility guidance becomes brittle because “knobs” appear to exist but don’t affect runtime behavior.

This does not change results under default settings (the defaults match the paper), but it can cause confusion and unintended comparisons during experimentation.

## Fix (Implementation Sketch)

Choose one:

1. **Wire the settings into runtime** (preferred):
   - Use `settings.MAX_ITERATIONS` as the default for `AgentConfig.max_steps`.
   - Use `settings.WSI_LONG_SIDE_TARGET` / `settings.OVERSAMPLING_BIAS` as defaults in `CropEngine.crop()` (or pass from agent runner).
   - Use `settings.PATCH_COUNT` / `settings.PATCH_SIZE` to parameterize patch sampling (or delete the settings and keep constants).
   - Use `settings.BOOTSTRAP_REPLICATES` in evaluation.

2. **Delete or demote the unused settings** if configuration is intentionally hard-coded, and document the true sources of defaults.

## Tests to Add

- A focused config wiring test that sets env vars (or constructs `Settings` with overrides) and asserts the corresponding runtime defaults change as expected.

## Acceptance Criteria

- Either env vars change runtime behavior consistently, or the unused settings are removed/documented so users aren’t misled.
