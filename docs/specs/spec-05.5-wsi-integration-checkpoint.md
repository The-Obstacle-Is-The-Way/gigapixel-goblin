# Spec-05.5: WSI Pipeline Integration Checkpoint

## Overview

**This is a PAUSE POINT.** Before proceeding to Spec-06, complete all integration tests below to catch P0-P4 issues in the WSI pipeline (Specs 02-05).

**Why pause here?**
- Specs 02-05 form a complete subsystem: read → coordinates → level select → crop
- Bugs here compound exponentially when the LLM loop is added
- Real `.svs` files expose edge cases mocks cannot catch
- This is the last chance to fix WSI issues before they're entangled with LLM logic

## Prerequisites

- [ ] Spec-02: WSI Data Layer — merged to main
- [ ] Spec-03: Coordinates — merged to main
- [ ] Spec-04: Level Selection — merged to main
- [ ] Spec-05: Cropping — merged to main
- [ ] All unit tests passing with ≥90% coverage

## Integration Test Checklist

### P0: Critical Path (Must Pass)

These tests validate the core navigation loop will function.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P0-1 | **Open real SVS file** | `WSIReader("test.svs")` with a real Aperio file | No exceptions, metadata populated | [ ] |
| P0-2 | **Thumbnail generation** | `reader.get_thumbnail((1024, 1024))` | Returns RGB PIL Image, correct aspect ratio | [ ] |
| P0-3 | **Read region at L0** | `reader.read_region((0, 0), level=0, size=(512, 512))` | Returns 512x512 RGB image | [ ] |
| P0-4 | **Read region at max level** | `reader.read_region((0, 0), level=max_level, size=(256, 256))` | Returns valid image (may be smaller if at edge) | [ ] |
| P0-5 | **Coordinate roundtrip** | `level_to_level0(level0_to_level(coord, ds), ds)` | Within ±downsample of original | [ ] |
| P0-6 | **Level selection for target** | `select_level(metadata, target_size=1000)` | Returns valid level index | [ ] |
| P0-7 | **Crop pipeline end-to-end** | `crop_region(reader, bbox, target_size=1000)` | Returns correctly sized RGB image | [ ] |

### P1: High Priority (Should Pass)

Edge cases that will cause subtle bugs in production.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P1-1 | **Boundary crop (right edge)** | Crop region extending past slide width | Graceful handling (clamp or pad) | [ ] |
| P1-2 | **Boundary crop (bottom edge)** | Crop region extending past slide height | Graceful handling (clamp or pad) | [ ] |
| P1-3 | **Tiny region (< target_size)** | Request 100x100 L0 region with target_size=1000 | Returns native resolution unchanged (never upsample) | [ ] |
| P1-4 | **Huge region (entire slide)** | Request full slide dimensions | Falls back to thumbnail or errors gracefully | [ ] |
| P1-5 | **Non-square aspect ratio** | Crop 1000x100 region | Maintains aspect ratio in output | [ ] |
| P1-6 | **Missing MPP metadata** | Open slide without mpp-x/mpp-y properties | `mpp_x=None`, no crashes | [ ] |
| P1-7 | **Non-power-of-2 downsample** | Slide with downsample=3.999 | Level selection still works | [ ] |

### P2: Medium Priority (Edge Cases)

Less common scenarios that could cause issues.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P2-1 | **Single-level slide** | Open slide with `level_count=1` | No index errors, level 0 used | [ ] |
| P2-2 | **Unicode path** | Open slide at path with Unicode chars | Opens successfully | [ ] |
| P2-3 | **Symlinked path** | Open slide via symlink | Resolves to real path | [ ] |
| P2-4 | **Very high resolution** | Slide with dimensions > 100,000 px | Coordinate math doesn't overflow | [ ] |
| P2-5 | **Different vendors** | Test with Aperio (.svs), Hamamatsu (.ndpi), Leica (.scn) | All parse metadata correctly | [ ] |

### P3: Low Priority (Nice to Have)

Performance and robustness.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P3-1 | **Memory under load** | Open 10 slides, read 100 regions each | Memory stable, no leaks | [ ] |
| P3-2 | **Concurrent reads** | Read regions from same slide in parallel | Thread-safe or clear error | [ ] |
| P3-3 | **Rapid open/close** | Open and close same slide 100 times | No resource exhaustion | [ ] |
| P3-4 | **Cache efficiency** | Call `get_metadata()` 1000 times | Returns cached value, <1ms each | [ ] |

### P4: Stretch (Future-Proofing)

Won't block progress but good to note.

| ID | Test | Notes | Status |
|----|------|-------|--------|
| P4-1 | **DICOM WSI support** | OpenSlide doesn't support DICOM natively | Document limitation | [ ] |
| P4-2 | **Cloud storage paths** | S3/GCS URLs | Would need separate implementation | [ ] |
| P4-3 | **Streaming large regions** | Avoid loading full region into memory | Future optimization | [ ] |

## Test Data Requirements

### Minimum Test Set

You need at least ONE real WSI file. Options:

1. **GTEx sample** (smallest, ~50-100MB):
   ```bash
   # Download from GTEx portal or use HuggingFace cache
   ```

2. **TCGA sample** (~200-500MB):
   ```bash
   # Requires GDC authentication
   ```

3. **OpenSlide test data** (~10MB synthetic):
   ```bash
   curl -LO https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-Small-Region.svs
   ```

### Recommended Test Set (for full coverage)

| File | Vendor | Size | Purpose |
|------|--------|------|---------|
| `CMU-1-Small-Region.svs` | Aperio | 10MB | Basic smoke test |
| `CMU-1.svs` | Aperio | 300MB | Full-size Aperio |
| `test.ndpi` | Hamamatsu | ~200MB | Vendor compatibility |
| `single-level.tiff` | Generic | ~5MB | Edge case: single level |

## Running Integration Tests

```bash
# Create integration test directory
mkdir -p tests/integration/wsi

# Run integration tests (requires test data)
uv run pytest tests/integration/wsi/ -v --tb=long

# Run with specific test file
WSI_TEST_FILE=/path/to/slide.svs uv run pytest tests/integration/wsi/ -v
```

## Sign-Off Criteria

**Proceed to Spec-06 when:**

- [ ] All P0 tests pass
- [ ] All P1 tests pass (or have documented workarounds)
- [ ] P2 tests reviewed (failures documented as known limitations)
- [ ] At least ONE real `.svs` file tested end-to-end
- [ ] No memory leaks observed in P3-1
- [ ] Integration test file committed to `tests/integration/wsi/`

## Discovered Issues Log

Document any issues found during integration testing:

| Date | ID | Severity | Description | Resolution |
|------|-----|----------|-------------|------------|
| | | | | |

## Notes

- This checkpoint should take 2-4 hours for thorough testing
- Do NOT skip this checkpoint to "save time" — debugging WSI issues inside the agent loop is 10x harder
- If you find P0/P1 issues, fix them before proceeding
- P2-P4 issues can be logged and addressed later
