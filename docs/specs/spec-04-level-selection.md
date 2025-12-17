# Spec-04: Pyramid Level Selection Algorithm

## Overview
This specification implements the core heuristic used by GIANT to select the optimal pyramid level for a given crop. The goal is to retrieve a region that, when scaled to the target size $S$ (default 1000px), retains maximum detail without unnecessary processing overhead. The paper specifies a distinct "oversampling bias" logic.

## Dependencies
- [Spec-02: WSI Data Layer & OpenSlide Integration](./spec-02-wsi-data.md)
- [Spec-03: Coordinate System & Geometry](./spec-03-coordinates.md)

## Acceptance Criteria
- [ ] `PyramidLevelSelector` class is implemented.
- [ ] `select_level` method accepts a `Region` (L0), `WSIMetadata`, and target size `S`.
- [ ] Implements the specific logic: `bias = 0.85`, check if projected size < S, shift level.
- [ ] Returns the optimal `level_index` (int) and the `downsample_factor` (float).
- [ ] Property-based tests verify the selected level is always valid (0 <= level < count).

## Technical Design

### Algorithm (Paper-Faithful)

**Paper Reference:** "We choose the pyramid level that will render the crop to a target long side (default S=1000 px) while biasing toward finer levels (oversampling bias 0.85)... If this level undershoots S, we move one level finer."

**Inputs:**
- `region`: Requested crop in Level-0 coordinates.
- `metadata.level_downsamples`: Pyramid downsample factors (relative to Level-0).
- `target_S`: Target long-side in pixels (default: 1000).
- `bias`: Oversampling bias (default: 0.85).

**Definitions:**
- `L0 = max(region.width, region.height)` — Region long-side in Level-0 pixels.
- For each level `k`: `Lk = L0 / metadata.level_downsamples[k]` — Projected size at level k.
- `target_native = target_S / bias` — The "ideal" native resolution before downsampling. By dividing by 0.85, we bias toward selecting levels that will oversample (requiring downscale to S) rather than undersample (requiring upscale).

**Steps:**
1. Compute `target_native = target_S / bias`.
2. Select `k*` as the level minimizing `abs(Lk - target_native)`.
   - **Tie-breaker:** Choose the **finer** level (smaller `k` / smaller downsample factor) to match "biasing toward finer levels".
3. **Undershoot correction:** If `Lk* < target_S`, move one level finer: `k* = max(k* - 1, 0)`.
   - Repeat until `Lk* >= target_S` OR `k* == 0` (can't go finer).
4. Return `k*` and `metadata.level_downsamples[k*]`.

**Invariant:** After this algorithm, we always downsample (or 1:1) to reach `target_S`, never upsample, unless the region is smaller than `target_S` at Level-0.

**Implementation:**
```python
def select_level(
    region: Region,
    metadata: WSIMetadata,
    target_size: int = 1000,
    bias: float = 0.85,
) -> SelectedLevel:
    L0 = max(region.width, region.height)
    target_native = target_size / bias

    # Find level closest to target_native, prefer finer on tie
    best_k = 0
    best_diff = float("inf")
    for k, ds in enumerate(metadata.level_downsamples):
        Lk = L0 / ds
        diff = abs(Lk - target_native)
        if diff < best_diff or (diff == best_diff and k < best_k):
            best_diff = diff
            best_k = k

    # Undershoot correction: ensure Lk >= target_size
    while best_k > 0:
        Lk = L0 / metadata.level_downsamples[best_k]
        if Lk >= target_size:
            break
        best_k -= 1

    return SelectedLevel(level=best_k, downsample=metadata.level_downsamples[best_k])
```

### Interface

```python
from typing import Protocol, NamedTuple

class SelectedLevel(NamedTuple):
    """Result of level selection."""
    level: int        # Pyramid level index (0 = finest)
    downsample: float # Downsample factor at this level

class LevelSelectorProtocol(Protocol):
    def select_level(
        self,
        region: Region,
        metadata: WSIMetadata,
        target_size: int = 1000,
        bias: float = 0.85,
    ) -> SelectedLevel: ...
```

## Test Plan

### Unit Tests
1.  **Standard Case:** Region 10,000px, S=1000, bias=0.85.
    - `target_native = 1000 / 0.85 ≈ 1176`.
    - Levels: ds=[1, 4, 16] → L=[10000, 2500, 625].
    - Closest to 1176: L1=2500 (diff=1324) vs L2=625 (diff=551) → L2 is closer.
    - Undershoot check: 625 < 1000 → move to L1.
    - L1=2500 >= 1000 → **Result: Level 1**.
2.  **Undershoot Correction:** Region 2000px, S=1000, bias=0.85.
    - `target_native ≈ 1176`.
    - Levels: ds=[1, 4] → L=[2000, 500].
    - Closest to 1176: L0=2000 (diff=824) vs L1=500 (diff=676) → L1 is closer.
    - Undershoot check: 500 < 1000 → move to L0.
    - L0=2000 >= 1000 → **Result: Level 0**.
3.  **Tie-breaker (prefer finer):** If two levels equidistant from target_native, pick smaller k.
4.  **Small region:** Region 500px at Level-0 with S=1000.
    - Even Level-0 undershoots. Return Level 0 (can't go finer).
5.  **Exact match:** Region where Lk == target_native exactly.

### Property-Based Tests
- `given(region_size=integers(100, 100000), target_s=integers(500, 2000), bias=floats(0.7, 1.0))`
- Verify selected level index is within bounds: `0 <= level < metadata.level_count`.
- Verify invariant: `Lk >= target_s OR level == 0` (never upsample unless forced).
- Verify determinism: same inputs → same output.

## File Structure
```text
src/giant/core/
├── __init__.py
├── level_selector.py
tests/unit/core/
└── test_level_selector.py
```
