# Bug Tracking - GIANT WSI + LLM Pipeline

## Summary

This directory tracks bugs discovered during integration checkpoint audits.

**Archive**: Fixed bugs are moved to `archive/` to keep the active list clean.

## Active Bugs

All bugs have been migrated to GitHub Issues for tracking:

- [GitHub Issues](https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin/issues)

| ID | Severity | Title | GitHub Issue |
|----|----------|-------|--------------|
| BUG-018 | P3 | Missing CONCH tool integration | [#33](https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin/issues/33) |
| BUG-020 | P3 | Official system prompts not incorporated | [#34](https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin/issues/34) |
| BUG-030 | P2 | Implementation audit findings | [#35](https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin/issues/35) |

## Local Audit Findings (Not Yet Filed)

The following issues were found during local reproduction/benchmark prep and should be filed to GitHub Issues when ready:

| ID | Severity | Title | Spec Doc | Where |
|----|----------|-------|----------|-------|
| BUG-033 | P0 | `make benchmark` uses wrong CLI args | [BUG-033-make-benchmark-uses-wrong-cli-args.md](BUG-033-make-benchmark-uses-wrong-cli-args.md) | `Makefile`, `docs/specs/spec-01-foundation.md`, `AGENTS.md` |
| BUG-034 | P0 | `make test` runs `live`/`cost` tests by default if keys are configured | [BUG-034-default-tests-trigger-live-api.md](BUG-034-default-tests-trigger-live-api.md) | `Makefile`, `tests/integration/llm/test_p0_critical.py` |
| BUG-035 | P1 | CLI exceptions may leak API keys via Rich “show locals” tracebacks | [BUG-035-cli-tracebacks-leak-secrets.md](BUG-035-cli-tracebacks-leak-secrets.md) | `src/giant/cli/main.py` (Typer defaults) |
| BUG-036 | P1 | TCGA download verification docs don’t match `gdc-client` layout | [BUG-036-wsi-readme-verification-gdc-layout.md](BUG-036-wsi-readme-verification-gdc-layout.md) | `data/wsi/README.md` |
| BUG-037 | P2 | Data acquisition verification snippet requires `pandas` (not a dependency) | [BUG-037-data-acquisition-verification-no-pandas.md](BUG-037-data-acquisition-verification-no-pandas.md) | `docs/DATA_ACQUISITION.md` |

## Archived (Fixed) Bugs

See `archive/` for historical bugs that have been resolved:

| ID | Title | Resolution |
|----|-------|------------|
| BUG-032 | Placeholder API keys treated as configured | Fixed (reject obvious placeholder secrets early) |
| BUG-031 | Answer extraction fails with multiple integers | Fixed (select first in-range option index) |
| BUG-029 | Low TCGA benchmark accuracy (investigation) | Fixed (AgentConfig T=20 default aligned to paper) |
| BUG-028 | Options not displayed in prompts (slidebench, expert_vqa) | Fixed (options appended when `{options}` missing) |
| BUG-027 | CSV options parsed as single-element list | Fixed (Python literal parsing + fail-loud validation) |
| BUG-026 | Model ID configuration scattered across codebase | Fixed (defaults centralized in `src/giant/llm/model_registry.py`) |
| BUG-025 | OpenAI Responses API rejects multi-turn conversations | Fixed (assistant messages use `output_text`) |
| BUG-023 | Axis guide labels use “K” abbreviation | Fixed (K-notation removed, strict integers used) |
| BUG-022 | MultiPathQA acquisition UX gaps | Fixed (`giant check-data` command added) |
| BUG-019 | Axis guide font fallback degrades legibility | Fixed (Strict font check added to overlay config) |
| BUG-021 | Prompt template edge case (max_steps=1) | Not reproducible (PromptBuilder uses final-step prompt) |
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

### Benchmark Prep Audit (2025-12-26)

**Goal**: Identify blockers and high-impact bugs before running the full MultiPathQA suite with an OpenAI API key (paper reproduction workflow).

**Paper anchor**: GIANT algorithm expects `T=20`, `S=1000`, oversampling bias `0.85`, and navigation via level-0 coordinate axis guides (see `_literature/markdown/giant/giant.md` Section 4.1).

**Quick validations run (safe / no live API calls)**:

- `make lint` / `make typecheck`
- `uv run pytest -m "not live and not cost"`
- `uv run giant check-data <dataset>` to confirm local WSI availability

**Findings (new bugs)**:

- **BUG-033 (P0)**: `make benchmark` is currently broken because it runs `uv run giant benchmark ./data/multipathqa`, but the CLI expects a dataset name (e.g., `tcga`). This drift also appears in `docs/specs/spec-01-foundation.md` and is referenced in `AGENTS.md`. Fix by updating examples/targets to `giant benchmark tcga --csv-path data/multipathqa/MultiPathQA.csv --wsi-root data/wsi` (and/or add per-dataset `make benchmark-tcga` targets).
- **BUG-034 (P0)**: `make test` / `make check` runs `pytest` without excluding `live`/`cost` tests. If `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` is configured, this will trigger real API calls and spend money unexpectedly. Fix by changing default test commands to exclude `live`/`cost` (and add an explicit opt-in target like `make test-live`).
- **BUG-035 (P1)**: When the CLI raises an exception, Rich tracebacks can print locals (including `Settings`), which may include API keys. Fix by disabling locals in Typer (`pretty_exceptions_show_locals=False`) and/or masking secrets (e.g., `SecretStr`).
- **BUG-036 (P1)**: `data/wsi/README.md` verification commands assume a flat `tcga/<filename>.svs` layout, but recommended downloads use `gdc-client` which stores files under `tcga/<file_id>/<uuid-suffixed filename>.svs`. This causes false “Missing” reports. Fix by recommending `giant check-data` (or updating shell checks to match resolver behavior).
- **BUG-037 (P2)**: `docs/DATA_ACQUISITION.md` includes a verification snippet that imports `pandas`, but `pandas` is not in `pyproject.toml` dependencies. Fix by rewriting the snippet using stdlib `csv` or directing users to `giant check-data`.

**Blocker status (data)**:

- TCGA WSIs are partially present; `giant check-data` currently reports missing files for `tcga`, `tcga_expert_vqa`, and `tcga_slidebench`.
- GTEx and PANDA WSIs are not present locally (`gtex`: missing 191/191, `panda`: missing 197/197), so full “all tasks” paper reproduction is blocked until those files are acquired.

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
- 2 reproducibility gaps remain open (BUG-018, BUG-020):
  - BUG-018: CONCH tool ablation requires gated CONCH access to reproduce Table 3
  - BUG-020: Paper’s OpenAI/Anthropic system prompts are in Supplementary Material (not available here)

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
