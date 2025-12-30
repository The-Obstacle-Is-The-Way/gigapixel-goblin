# BUG-039 Backlog: Medium & Low Priority Leads

**Status**: OPEN (unvalidated swarm leads for future maintenance)
**Source**: 8-agent swarm audit (2025-12-30)
**Parent**: [BUG-039-comprehensive-swarm-audit.md](../archive/bugs/BUG-039-comprehensive-swarm-audit.md)

## Context

The BUG-039 swarm audit identified 52 potential issues. Critical (C1-C6) and High (H1-H12) were triaged in the senior review. The Medium and Low leads below are **unvalidated** - they may be real bugs, false positives, or already-handled edge cases. Each requires reproduction before treating as a confirmed bug.

---

## Medium Severity Leads (P2 - Maintenance)

| ID | File | Issue | Notes |
|----|------|-------|-------|
| M1 | `wsi_resolver.py:176-183` | Broken symlinks fail resolution | Edge case |
| M2 | `answer_extraction.py:85-93` | Substring matching ambiguity | Checked: longest-first matching already handles this |
| M3 | `metrics.py:40-76` | Out-of-range predictions ignored | Checked: correct behavior (wrong = wrong) |
| M4 | `wsi_resolver.py:111-141` | DICOM naming assumption | C6 fix may cover this |
| M5 | `runner.py:308-310` | Options parsing whitespace | H2 fix may cover this |
| M6 | `runner.py:187` | UTF-8 errors not handled | Edge case for corrupted CSVs |
| M7 | `circuit_breaker.py` | Race condition in state | Retry limiting, not correctness |
| M8 | `anthropic_client.py:92-98` | JSON-string action validation | May be covered by existing validation |
| M9 | `level_selector.py:174-175` | Float precision loss | Very minor |
| M10 | `runner.py:636-639` | Cost accumulation race | C3/H4 fix may cover this |
| M11 | `context.py:64-79` | Step index mismatch | Checked: intentional 0-indexed internal, 1-indexed display |
| M12 | `templates.py:92-96` | Missing {options} in final step | BUG-028 fix may cover this |
| M13 | `builder.py:51-103` | No dynamic options support | Feature request, not a bug |
| M14 | `wsi_reader.py:129-146` | Silent vendor/MPP failures | Logging improvement |
| M15 | `wsi_reader.py:136-146` | Level dimension validation | Edge case |
| M16 | `wsi_reader.py:232-245` | Overly broad exception | Code quality |
| M17 | `crop_engine.py:184-188` | Returned image size not verified | Edge case |
| M18 | `overlay.py:184-203` | Font warning in batch mode | Logging annoyance |
| M19 | `types.py:163-181` | int() vs round() in coordinates | 1px off, unlikely to matter |
| M20 | `runner.py:630-634` | Budget check timing | C3/H4 fix may cover this |
| M21 | `runner.py:335-348` | Empty options list handling | Edge case |
| M22 | `runner.py:187-196` | CSV fieldname validation | May be covered |

---

## Low Severity Leads (P3 - Nice to Have)

| ID | File | Issue | Notes |
|----|------|-------|-------|
| L1 | `wsi_resolver.py:95` | Greedy glob pattern | Performance |
| L2 | `runner.py:43` | Sentinel value collision | Unlikely |
| L3 | `overlay.py:131-154` | Label rounding truncation | Display only |
| L4 | `overlay.py:205-216` | No thousands separators | Display only |
| L5 | `validators.py:45-90` | Defensive dimension check | Hardening |
| L6 | `primitives.py:129-152` | from_corners error message | UX |
| L7 | `types.py:205-223` | size_at_level min(1px) undocumented | Documentation |
| L8 | `crop_engine.py:150-154` | JPEG quality warning | Logging |
| L9 | `crop_engine.py:234-241` | 1px dimension possible | Edge case |
| L10 | `anthropic_client.py:195-200` | Retry count for images | Tuning |
| L11 | `main.py:97-103` | Budget 0.0 ambiguity | UX |
| L12 | `runner.py:432-439` | Missing logging for skipped items | Observability |

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

| Lead | Verdict | Evidence |
|------|---------|----------|
| M2 | NOT A BUG | Longest-first matching at line 88-90 handles substring ambiguity |
| M3 | NOT A BUG | Out-of-range predictions correctly count as wrong (no match = wrong) |
| M11 | NOT A BUG | Intentional: internal 0-indexed, display 1-indexed (line 308 shows +1) |
