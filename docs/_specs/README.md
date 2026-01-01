# Specs

This directory contains active implementation/change specs and checkpoint reports.

## Active Specs

- `BUG-040-P1-2-openai-stepresponse-schema-hardening.md` (DRAFT)

## Archived Specs

All original GIANT implementation specs (Spec-01 → Spec-12 + checkpoints) are archived.

**Location:** `docs/_archive/specs/README.md`

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

**All 5 MultiPathQA benchmarks complete** (2025-12-30):

| Benchmark | Our Result | Paper (x1) | Status |
|-----------|------------|------------|--------|
| GTEx | **70.3%** | 53.7% | Exceeds paper |
| ExpertVQA | **60.1%** | 57.0% | Exceeds paper |
| SlideBench | **51.8%** | 58.9% | Below paper |
| TCGA | **26.2%** | 32.3% | Below paper |
| PANDA | **20.3%** | 23.2% | Below paper |

Total cost: $124.64 across 934 questions (862 WSIs).
