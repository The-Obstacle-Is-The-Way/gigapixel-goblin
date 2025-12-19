# Bug Tracking - GIANT WSI + LLM Pipeline

## Summary

This directory tracks bugs discovered during integration checkpoint audits.

**Archive**: Fixed bugs are moved to `archive/` to keep the active list clean.

## Active Bugs

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| BUG-015 | P3 | Visualizer missing images/overlays | Open |
| BUG-016 | P2 | Agent executes crop when `max_steps=1` | Open |
| BUG-017 | P4 | TCGA downloader trusts remote `file_name` for paths | Open |

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
| BUG-010 | MPP Nullable No Guards | Archived (future-proofing note, no active bug) |
| BUG-011 | Unused GeometryValidator | Fixed in Spec-09 (now used in agent runner) |
| BUG-012 | HF Download Silent Auth | Debug log added |
| BUG-013 | Silent Zero-Cost on Missing Usage Data | Fail fast on missing usage + tests |
| BUG-014 | Environment Secrets Management Gap | .env docs + test fixes + schema fixes |

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

- 61 integration tests passing (+ 2 new missing-usage tests)
- P0-2 requirements fully covered
- 2 bugs documented + fixed (BUG-013, BUG-014)
- 11 fixed bugs archived
- Fixed: Anthropic JSON string parsing, OpenAI oneOf schema issue
- Fixed: Test skipif now detects keys from .env file

### Spec-12 CLI Merge + Bug Housekeeping (2025-12-19)

**Audited**: BUG-010, BUG-011 from deferred list

**Findings**:

- BUG-010 (MPP nullable): Not a bug, just future-proofing note. Archived.
- BUG-011 (GeometryValidator unused): Fixed in Spec-09. Archived.
- All active bugs cleared. Zero active bugs remaining.

### Audit Bug Hunt (P0-P4) (2025-12-19)

**Audited**: Spec-09 to Spec-12 integration surfaces (agent loop, eval, CLI, visualizer, download helpers).

**Findings**:

- 3 new bugs documented (BUG-015, BUG-016, BUG-017)
- No new P0/P1 blockers found

### Spec-05.5 WSI Integration Checkpoint (2025-12-17)

**Audited**: Specs 01-05 (WSI data layer, cropping, levels)

**Findings**:

- 17 WSI integration tests added
- 12 bugs documented
- 9 bugs fixed
- 2 deferred to Spec-09 (BUG-010, BUG-011) — now resolved
