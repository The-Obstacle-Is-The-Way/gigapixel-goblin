# Specs - Archived

All 15 specs have been completed and archived.

**Location:** [docs/archive/specs/README.md](../archive/specs/README.md)

## Summary

| Spec | Status | Archived |
|------|--------|----------|
| Spec-01: Foundation | Complete | 2025-12-29 |
| Spec-02: WSI Data | Complete | 2025-12-29 |
| Spec-03: Coordinates | Complete | 2025-12-29 |
| Spec-04: Level Selection | Complete | 2025-12-29 |
| Spec-05: Cropping | Complete | 2025-12-29 |
| Spec-05.5: WSI Checkpoint | Passed | 2025-12-29 |
| Spec-06: LLM Provider | Complete | 2025-12-29 |
| Spec-07: Navigation Prompt | Complete | 2025-12-29 |
| Spec-08: Context Manager | Complete | 2025-12-29 |
| Spec-08.5: LLM Checkpoint | Passed | 2025-12-29 |
| Spec-09: GIANT Agent | Complete | 2025-12-29 |
| Spec-10: Evaluation | Complete | 2025-12-29 |
| Spec-11: CLAM Integration | Complete | 2025-12-29 |
| Spec-11.5: E2E Checkpoint | Passed | 2025-12-29 |
| Spec-12: CLI & API | Complete | 2025-12-29 |

## Validation Results

Full E2E validation completed on 2025-12-29. After BUG-038/BUG-039 fixes, we
rescored the saved artifacts (no new LLM calls) on scored items only (excluding
the 6 parse failures per benchmark caused by the pre-fix OpenAI JSON parser):
- **TCGA**: 26.2% balanced accuracy (paper: 32.3%)
- **GTEx**: 70.3% balanced accuracy (paper: 60.7%)
- **PANDA**: 20.3% balanced accuracy (paper: 23.2%)

Total cost: $95.73 across 609 WSIs.
