# Bug Tracking - GIANT WSI + LLM Pipeline

## Summary

This directory tracks bugs discovered during integration checkpoint audits.

**Archive**: Fixed bugs are moved to `../_archive/bugs/` to keep the active list clean.

## Active Bugs

Bugs are tracked in GitHub Issues when available (LOCAL items are not yet filed):

- [GitHub Issues](https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin/issues)

No active local bug docs. See `../_archive/bugs/`.

## Local Audit Findings (Not Yet Filed)

### Comprehensive E2E Bug Audit (2025-12-29)

**BUG-038**: 8-agent swarm audit produced **12 findings** (11 bugs + 1 retracted) across the codebase:

| Severity | Count | Critical Bugs |
|----------|-------|---------------|
| **CRITICAL** | 2 | ~~PANDA null handling~~, ~~JSON "Extra data" errors~~ ✅ FIXED |
| **HIGH** | 3 | ~~JSON extraction~~, ~~Anthropic JSON-string parsing clarity~~, ~~token count None handling~~ ✅ FIXED |
| **MEDIUM** | 4 | ~~Retry counter~~ ✅ FIXED, ~~base64~~ ✅ FIXED, ~~recursion~~ ✅ FIXED, ~~action types~~ ✅ FIXED |
| **LOW** | 2 | ~~Comments~~ ✅ FIXED, ~~validation~~ ✅ FIXED |

Note: One originally-reported medium finding (step guard) was retracted after review in `do../_archive/bugs/BUG-038-comprehensive-audit.md`.

**Primary Impact**:
- PANDA improved from **9.7% → 20.3% balanced accuracy** on scored items only (excluding the 6 pre-fix OpenAI parse failures); no new LLM calls were needed to rescore the saved artifacts after BUG-038 fixes
- PANDA outputs `"isup_grade": null` in **115/197** items; the pre-fix extractor turned many of these into extraction failures or bad integer fallbacks (fixed by B1)
- OpenAI `"Extra data"` parsing caused **18/609 hard failures (3.0%)** across all benchmarks and triggered frequent retries (fixed by B2)
- Reported run costs can still be a lower bound: if parsing fails for any reason, the current clients raise before usage is accumulated; B2 removes the common “trailing text” parse failures

**Status**: COMPLETED & ARCHIVED — 11 bug fixes landed (B1–B5, B7–B12) and 1 false-positive retracted (B6).

See [BUG-038-comprehensive-audit.md](../_archive/bugs/BUG-038-comprehensive-audit.md) for full analysis (archived).
See [BUG-038-panda-answer-extraction.md](../_archive/bugs/BUG-038-panda-answer-extraction.md) for original PANDA analysis.

### Comprehensive Swarm Audit (2025-12-30)

**BUG-039**: 8-agent swarm audit followed by senior review.

| Severity | Total | Fixed | Retracted | Not A Bug |
|----------|-------|-------|-----------|-----------|
| Critical | 6 | 5 | 1 | 0 |
| High | 12 | 7 | 5 | 0 |
| Medium | 22 | 2 | 0 | 20 |
| Low | 12 | 1 | 0 | 11 |

**Status**: COMPLETED & ARCHIVED
- Critical + High: See [BUG-039-comprehensive-swarm-audit.md](../_archive/bugs/BUG-039-comprehensive-swarm-audit.md)
- Medium + Low: See [BUG-039-backlog.md](../_archive/bugs/BUG-039-backlog.md) (all validated, 3 fixed, 31 not bugs)

## Archived (Fixed) Bugs

See `../_archive/bugs/` for historical bugs that have been resolved:

| ID | Title | Resolution |
|----|-------|------------|
| BUG-047 | Unused “Paper Parameter” Settings | Fixed (wired Settings defaults + bootstrap config) |
| BUG-046 | Patch Baselines Reuse Same Patches Across Runs | Fixed (resample per run) |
| BUG-045 | CONCH Disabled Retry Guard Never Trips | Fixed (retry loop without step consumption) |
| BUG-044 | Provider Rate Limiter Does Not Cover Tenacity Retries | Fixed (rate limit per retry attempt) |
| BUG-043 | Invalid Region Retry Premature Exit | Fixed (bounded invalid-region correction loop) |
| BUG-040 | Benchmark Underperformance Audit | Archived (audit completed; follow-ups addressed) |
| BUG-042 | Paper-Fidelity Gap — Patch Baseline Not Majority Vote | Fixed (added `patch_vote` mode) |
| BUG-041 | Paper-Fidelity Gap — Fixed Iteration Enforcement Missing | Fixed (added `enforce_fixed_iterations` paper-fidelity mode) |
| BUG-039 | Comprehensive Swarm Audit | Critical + high issues fixed; false positives retracted |
| BUG-038 | Comprehensive E2E Bug Audit | 11 fixes landed; 1 false-positive retracted (B6) |
| BUG-037 | Data acquisition verification requires `pandas` | Fixed (use `giant check-data` CLI instead) |
| BUG-036 | WSI README verification assumes flat TCGA layout | Fixed (recommend `giant check-data`, handles both layouts) |
| BUG-035 | CLI exceptions may leak API keys in tracebacks | Fixed (`pretty_exceptions_show_locals=False`) |
| BUG-034 | Default tests trigger live API calls | Fixed (exclude live/cost markers + `GIANT_RUN_LIVE_TESTS` gate) |
| BUG-033 | `make benchmark` uses wrong CLI args | Fixed (Makefile uses `$(DATASET)` + fail-fast validation) |
| BUG-032 | Placeholder API keys treated as configured | Fixed (reject obvious placeholder secrets early) |
| BUG-031 | Answer extraction fails with multiple integers | Fixed (select first in-range option index) |
| BUG-030 | Implementation audit findings | Closed (triage complete; GitHub issue #35 closed) |
| BUG-029 | Low TCGA benchmark accuracy (investigation) | Fixed (AgentConfig T=20 default aligned to paper) |
| BUG-028 | Options not displayed in prompts (slidebench, expert_vqa) | Fixed (options appended when `{options}` missing) |
| BUG-027 | CSV options parsed as single-element list | Fixed (Python literal parsing + fail-loud validation) |
| BUG-026 | Model ID configuration scattered across codebase | Fixed (defaults centralized in `src/giant/llm/model_registry.py`) |
| BUG-025 | OpenAI Responses API rejects multi-turn conversations | Fixed (assistant messages use `output_text`) |
| BUG-023 | Axis guide labels use “K” abbreviation | Fixed (K-notation removed, strict integers used) |
| BUG-022 | MultiPathQA acquisition UX gaps | Fixed (`giant check-data` command added) |
| BUG-019 | Axis guide font fallback degrades legibility | Fixed (Strict font check added to overlay config) |
| BUG-021 | Prompt template edge case (max_steps=1) | Not reproducible (PromptBuilder uses final-step prompt) |
| BUG-020 | Official system prompts not incorporated | Resolved in code (supports `GIANT_SYSTEM_PROMPT*` overrides) |
| BUG-018 | Missing CONCH tool integration | Implemented (optional `conch` action; user-supplied scorer required) |
| BUG-017 | TCGA downloader path traversal | Path validation added |
| BUG-016 | Agent crop on max_steps=1 | Step guard added |
| BUG-015 | Visualizer missing images/overlays | Trajectory metadata + HTML/CSS updates |
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
| BUG-012 | HF Download Silent Auth | Debug log + empty-token guard added |
| BUG-013 | Silent Zero-Cost on Missing Usage Data | Fail fast on missing usage + tests |
| BUG-014 | Environment Secrets Management Gap | .env docs + test fixes + schema fixes |

## Severity Definitions

- **P0 (Critical)**: Blocks progress. Must fix immediately.
- **P1 (High)**: Will cause production bugs. Should fix before next spec.
- **P2 (Medium)**: Edge cases. Can document and address later.
- **P3 (Low)**: Nice to have. Future optimization.
- **P4 (Future)**: Scaffolding for upcoming specs.

## Checkpoint History

### Benchmark Prep Audit (2025-12-26)

**Goal**: Identify blockers and high-impact bugs before running the full MultiPathQA suite with an OpenAI API key (paper reproduction workflow).

**Paper anchor**: GIANT algorithm expects `T=20`, `S=1000`, oversampling bias `0.85`, and navigation via level-0 coordinate axis guides (see `_literature/markdown/giant/giant.md` Section 4.1).

**Quick validations run (safe / no live API calls)**:

- `make lint` / `make typecheck`
- `uv run pytest -m "not live and not cost"`
- `uv run giant check-data <dataset>` to confirm local WSI availability

**Findings (bugs identified and fixed)**:

- **BUG-033 (P0)**: ✅ Fixed. Makefile now uses `$(or $(DATASET),tcga)` + per-dataset targets (`benchmark-tcga`, etc.). CLI runner validates dataset before creating LLM provider (fail-fast).
- **BUG-034 (P0)**: ✅ Fixed. `make test` excludes `live`/`cost` markers. Live tests require explicit `GIANT_RUN_LIVE_TESTS=1` environment variable.
- **BUG-035 (P1)**: ✅ Fixed. Typer app sets `pretty_exceptions_show_locals=False`. Regression tests verify secrets don't leak.
- **BUG-036 (P1)**: ✅ Fixed. `data/wsi/README.md` now recommends `giant check-data` which handles both flat and gdc-client layouts.
- **BUG-037 (P2)**: ✅ Fixed. `docs/data-acquisition.md` verification section uses `giant check-data` CLI (no pandas dependency).

**Blocker status (data)**:

- TCGA WSIs are partially present; `giant check-data` currently reports missing files for `tcga`, `tcga_expert_vqa`, and `tcga_slidebench`.
- (As of 2025-12-26) GTEx and PANDA WSIs were not present locally, so full “all tasks” paper reproduction was blocked until those files were acquired.
- Update (2025-12-30): GTEx and PANDA WSIs have since been downloaded under `data/wsi/`, and full benchmarks were run (see `docs/results/benchmark-results.md`).

### Benchmark Execution Bug Hunt (2025-12-21)

**Audited**: Full OpenAI benchmark run on 25 available TCGA questions.

**Findings**:

- 88% answer extraction failure rate (22/25 questions)
- **BUG-027 (P1)**: CSV options are Python list literals, but loader assumed JSON and produced a 1-element list fallback.
- **BUG-028 (P2)**: `tcga_slidebench` and `tcga_expert_vqa` have options but prompts omit `{options}`, so the model never sees choices.
- Cost: $0.99 wasted on unusable benchmark results

**Status**: Fixed in code + unit tests; re-run benchmark once WSIs are available.

### E2E Validation Bug Hunt (2025-12-20)

**Audited**: Full E2E inference with real WSI and OpenAI API.

**Findings**:

- 1 P0 bug fixed (BUG-025): OpenAI Responses API rejects multi-turn conversations
- Root cause: `message_content_to_openai()` used `input_text` for all content, but assistant messages require `output_text`
- Test gap: Added regression test for assistant message content types
- Additional test gaps identified but not blocking (circuit breaker cooldown, provider validation)

### Audit (2025-12-19) - Paper Gap Analysis

**Audited**: Full codebase vs GIANT paper and Specs.

**Findings**:
- 6 new bug reports filed (BUG-018 to BUG-023).
- 3 bugs fixed immediately (BUG-019, BUG-022, BUG-023).
- 1 bug invalid (BUG-021).
- 2 reproducibility gaps were addressed in code (BUG-018, BUG-020):
  - BUG-018: CONCH tool path implemented behind a feature flag; still requires gated weights / user-supplied scorer
  - BUG-020: Provider-specific system prompt overrides supported; still requires Supplementary Material text for verbatim reproduction

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
- Deferred list cleared (BUG-010/BUG-011 archived).

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
