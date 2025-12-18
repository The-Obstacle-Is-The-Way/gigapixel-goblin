# Bug Tracking - GIANT WSI + LLM Pipeline

## Summary

This directory tracks bugs discovered during integration checkpoint audits.

**Archive**: Fixed bugs are moved to `archive/` to keep the active list clean.

## Active Bugs

### P3 - Low Priority (Deferred / Future-Proofing)

| ID | Title | Status |
|----|-------|--------|
| [BUG-010](./BUG-010-mpp-nullable-no-guards.md) | Optional MPP Needs Helper/Guards When Used | Open (Future) |
| [BUG-011](./BUG-011-unused-geometry-validator.md) | GeometryValidator Is Staged for Spec-09 | Open (Deferred) |

## Archived (Fixed) Bugs

See `archive/` for historical bugs that have been resolved:

| ID | Title | Resolution |
|----|-------|------------|
| BUG-001 | Boundary Crop Behavior | Documented + tested |
| BUG-002 | Spec Contradiction on Upsampling | Spec-05.5 updated |
| BUG-003 | Huge Region No Protection | Memory guard added |
| BUG-004 | Missing Integration Tests | Integration tests added |
| BUG-005 | Single-Level Slide Untested | Unit tests added |
| BUG-007 | Test Suite Mocked (claim inaccurate) | Documentation corrected |
| BUG-008 | API Keys Silent None | ConfigError added |
| BUG-009 | Font Loading Silent Fallback | Warning log added |
| BUG-012 | HF Download Silent Auth | Debug log added |
| BUG-013 | Silent Zero-Cost on Missing Usage Data | Fail fast on missing usage + tests |

## Severity Definitions

- **P0 (Critical)**: Blocks progress. Must fix immediately.
- **P1 (High)**: Will cause production bugs. Should fix before next spec.
- **P2 (Medium)**: Edge cases. Can document and address later.
- **P3 (Low)**: Nice to have. Future optimization.
- **P4 (Future)**: Scaffolding for upcoming specs.

## Checkpoint History

### Spec-08.5 LLM Integration Checkpoint (2025-12-18)

**Audited**: Specs 06-08 (LLM Provider, Navigation Prompts, Context Manager)

**Findings**:
- 59 integration tests passing
- P0-2 requirements fully covered
- 1 new bug documented + fixed (BUG-013)
- 10 fixed bugs archived

### Spec-05.5 WSI Integration Checkpoint (2025-12-17)

**Audited**: Specs 01-05 (WSI data layer, cropping, levels)

**Findings**:
- 17 WSI integration tests added
- 12 bugs documented
- 9 bugs fixed
- 2 deferred to Spec-09 (BUG-010, BUG-011)
