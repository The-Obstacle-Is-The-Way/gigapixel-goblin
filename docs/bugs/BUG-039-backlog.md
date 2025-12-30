# BUG-039 Backlog: Medium & Low Priority Leads

**Status**: VALIDATED (all leads have verdicts)
**Source**: 8-agent swarm audit (2025-12-30)
**Parent**: [BUG-039-comprehensive-swarm-audit.md](../archive/bugs/BUG-039-comprehensive-swarm-audit.md)

## Context

The BUG-039 swarm audit identified 52 potential issues. Critical (C1-C6) and High
(H1-H12) were triaged in the senior review. The Medium and Low leads below were
captured as hypotheses and are now fully validated.

This document is now the SSOT for the Medium/Low backlog: every lead has a
verdict with code evidence. The original swarm file:line references may not
match the current repo (e.g., `wsi_reader.py` is now `src/giant/wsi/reader.py`).

---

## Summary (2025-12-30)

- Confirmed bugs fixed: **2** (`M21`, `M22`)
- Doc fixes applied: **1** (`L7`)
- Not bugs / already handled / non-actionable: **31**

## Medium Severity Leads (P2 - Maintenance)

| ID | File (from swarm) | Issue | Verdict | Evidence (code) |
|----|-------------------|-------|---------|-----------------|
| M1 | `wsi_resolver.py:176-183` | Broken symlinks fail resolution | NOT A BUG | `src/giant/eval/wsi_resolver.py:resolve()` intentionally uses `Path.exists()`; broken symlink means target is unavailable → correct to treat as missing and raise `FileNotFoundError`. |
| M2 | `answer_extraction.py:85-93` | Substring matching ambiguity | NOT A BUG | `src/giant/eval/answer_extraction.py:_extract_from_options()` sorts options longest-first to avoid substring false positives. |
| M3 | `metrics.py:40-76` | Out-of-range predictions ignored | NOT A BUG | `src/giant/eval/metrics.py:balanced_accuracy()` computes recall per *truth* class; any non-matching prediction (including out-of-range) counts as wrong. |
| M4 | `wsi_resolver.py:111-141` | DICOM naming assumption | NOT A BUG | `src/giant/eval/wsi_resolver.py:_try_resolve_dicom_directory()` uses `image_path` stem as directory name; absent extra metadata, this is the only deterministic mapping and matches the benchmark layout. |
| M5 | `runner.py:308-310` | Options parsing whitespace | NOT A BUG | `src/giant/eval/runner.py:_parse_options()` strips the field and each option, then filters empty strings. |
| M6 | `runner.py:187` | UTF-8 errors not handled | NOT A BUG | Decode failures should surface; MultiPathQA CSV is required to be UTF-8. (We now open with `encoding="utf-8-sig"` to tolerate BOM.) |
| M7 | `circuit_breaker.py` | Race condition in state | NOT A BUG | `src/giant/llm/circuit_breaker.py` methods are synchronous; in asyncio they run atomically between awaits. Thread-safety is not a requirement in current usage. |
| M8 | `anthropic_client.py:92-98` | JSON-string action validation | NOT A BUG | `src/giant/llm/anthropic_client.py:_parse_tool_use_to_step_response()` parses stringified `action` and raises `LLMParseError` with the real `JSONDecodeError` cause. |
| M9 | `level_selector.py:174-175` | Float precision loss | NOT A BUG | `src/giant/core/level_selector.py:_find_closest_level()` uses float math for level selection; small float error is immaterial to tie-breaking and correctness. |
| M10 | `runner.py:636-639` | Cost accumulation race | NOT A BUG | `src/giant/eval/runner.py:_run_worker()` updates `budget_state` and checkpoints under `checkpoint_lock`. Additionally, `budget_usd` requires `max_concurrent==1`. |
| M11 | `context.py:64-79` | Step index mismatch | NOT A BUG | `src/giant/agent/context.py` uses 0-indexed `Turn.step_index` internally and exposes a 1-indexed `current_step` for prompts. |
| M12 | `templates.py:92-96` | Missing {options} in final step | NOT A BUG | Options are injected into the *question/prompt* string at CSV-load time (`BenchmarkRunner._inject_options()`), and `{question}` is included in final-step prompts. |
| M13 | `builder.py:51-103` | No dynamic options support | NOT A BUG | Not required: options are already embedded in `question`/prompt; “dynamic options per step” would be a feature request. |
| M14 | `wsi_reader.py:129-146` | Silent vendor/MPP failures | NOT A BUG | `src/giant/wsi/reader.py:get_metadata()` treats MPP as optional and returns `None` when missing/invalid; logging would be an enhancement, not correctness. |
| M15 | `wsi_reader.py:136-146` | Level dimension validation | NOT A BUG | `src/giant/wsi/reader.py` trusts OpenSlide invariants (`level_count`, `level_dimensions`, `level_downsamples`). Validation would be redundant. |
| M16 | `wsi_reader.py:232-245` | Overly broad exception | NOT A BUG | `src/giant/wsi/reader.py:read_region()` wraps “anything OpenSlide/PIL throws” into a typed `WSIReadError` for consistent upstream handling. |
| M17 | `crop_engine.py:184-188` | Returned image size not verified | NOT A BUG | OpenSlide returns an image of the requested size; out-of-bounds reads are padded. There is no correctness signal available by re-checking size. |
| M18 | `overlay.py:184-203` | Font warning in batch mode | NOT A BUG | `src/giant/geometry/overlay.py` warns once per process unless logger handlers duplicate; this is observability/UX, not correctness. |
| M19 | `types.py:163-181` | int() vs round() in coordinates | NOT A BUG | `src/giant/wsi/types.py:level0_to_level()` uses truncation by design; unit tests already account for ≤1-downsample-unit drift. |
| M20 | `runner.py:630-634` | Budget check timing | NOT A BUG | Budget is best-effort because per-item cost is only known after completion; sequential budget mode prevents concurrent overshoot. |
| M21 | `runner.py:335-348` | Empty options list handling | FIXED | `src/giant/eval/runner.py:load_benchmark_items()` now treats parsed `[]` as “no options” (`options=None`) to avoid invalid 1..0 truth-label validation. |
| M22 | `runner.py:187-196` | CSV fieldname validation | FIXED | `src/giant/eval/runner.py:load_benchmark_items()` now validates required headers (`benchmark_name`, `image_path`, `answer`) and raises a clear `ValueError` (also BOM-tolerant via `utf-8-sig`). |

---

## Low Severity Leads (P3 - Nice to Have)

| ID | File (from swarm) | Issue | Verdict | Evidence (code) |
|----|-------------------|-------|---------|-----------------|
| L1 | `wsi_resolver.py:95` | Greedy glob pattern | NOT A BUG | `src/giant/eval/wsi_resolver.py:_try_resolve_uuid_suffixed_filename()` filters `glob()` results to `p.is_file()` and raises on ambiguity; correctness preserved. |
| L2 | `runner.py:43` | Sentinel value collision | NOT A BUG | `src/giant/eval/runner.py` uses `_MISSING_LABEL_SENTINEL=-1`; truth labels are validated to be non-negative (PANDA) or ≥1 (multi-choice). |
| L3 | `overlay.py:131-154` | Label rounding truncation | NOT A BUG | `src/giant/geometry/overlay.py` uses integer labels for display; does not affect crop math (the agent reads the image, not these strings). |
| L4 | `overlay.py:205-216` | No thousands separators | NOT A BUG | Cosmetic only; coordinates are absolute pixel values and intentionally unformatted. |
| L5 | `validators.py:45-90` | Defensive dimension check | NOT A BUG | `src/giant/geometry/validators.py:GeometryValidator.validate()` already checks `right<=width` and `bottom<=height` and raises a structured `ValidationError`. |
| L6 | `primitives.py:129-152` | from_corners error message | NOT A BUG | `src/giant/geometry/primitives.py:Region.from_corners()` delegates invalid-width/height reporting to Pydantic field constraints; message quality is UX only. |
| L7 | `types.py:205-223` | size_at_level min(1px) undocumented | FIXED | `src/giant/wsi/types.py:size_at_level()` docstring now documents the 1px minimum clamp (behavior already covered by tests). |
| L8 | `crop_engine.py:150-154` | JPEG quality warning | NOT A BUG | `src/giant/core/crop_engine.py:crop()` validates `jpeg_quality` and raises; “warning” would be policy, not correctness. |
| L9 | `crop_engine.py:234-241` | 1px dimension possible | NOT A BUG | `_resize_to_target()` clamps the short side to at least 1px; this is intentional to avoid zero-sized images. |
| L10 | `anthropic_client.py:195-200` | Retry count for images | NOT A BUG | `src/giant/llm/anthropic_client.py` retry policy is operational tuning, not a correctness defect. |
| L11 | `main.py:97-103` | Budget 0.0 ambiguity | NOT A BUG | CLI treats `--budget-usd 0` as disabled via `budget_usd if budget_usd > 0 else None` in `src/giant/cli/runners.py`. |
| L12 | `runner.py:432-439` | Missing logging for skipped items | NOT A BUG | Skips are intentional (`is_valid!=true` or benchmark mismatch); more logging is observability, not correctness. |

---

## Test Coverage Gaps (from swarm audit)

**Reported Coverage**: 92.18% (826 tests at audit time; now 843 tests)

**Critical Gaps**:
- CLI: 73% (exception handlers untested)
- WSI Resolver: 76% (edge case paths)
- Agent Runner: 88% (error recovery branches)

**Missing Scenarios**:
- Empty message content validation
- Corrupted WSI files
- Network timeout recovery
- Concurrent budget exhaustion
- Invalid base64 detection

---

## How to Use This Document

1. **Before working on a lead**: Reproduce it first. Many may be false positives.
2. **When fixing a lead**: Move it to a new BUG-040+ ticket with full spec.
3. **Spot-checked leads**: M2, M3, M11 were checked and are NOT bugs (see Notes).
4. **Related fixes**: Some leads may already be covered by BUG-038/039 fixes (see Notes).

---

## Quick Spot-Check Results (2025-12-30)

All Medium/Low leads have been validated; see the tables above.
