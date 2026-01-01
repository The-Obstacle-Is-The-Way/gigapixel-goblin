# Technical Debt: P3 Low Priority Items (COMPLETED)

**Priority:** P3 (Low)
**Total Items:** 0 remaining
**Effort:** Trivial–Small each
**Status:** ✅ COMPLETED (all items implemented)
**Last Verified:** 2026-01-01

---

## Overview (Implemented)

| ID | Issue | Disposition | Primary Location |
|----|-------|-------------|------------------|
| P3-1 | Circuit breaker state changes on `.state` read | DONE | `src/giant/llm/circuit_breaker.py` |
| P3-2 | No feedback when CONCH disabled | DONE | `src/giant/agent/runner.py`, `src/giant/agent/context.py` |
| P3-3 | Sentinel `-1` for missing labels | DONE | `src/giant/eval/runner.py` |
| P3-4 | `assert` used for runtime validation | DONE | `src/giant/agent/runner.py` |
| P3-5 | PIL typing import duplication | DONE | `src/giant/agent/runner.py` |
| P3-6 | Nested PIL import anti-pattern | DONE | `src/giant/agent/runner.py` |
| P3-7 | Negative `budget_usd` accepted | DONE | `src/giant/agent/runner.py` |
| P3-8 | Tests use Mock without spec | DONE | `tests/unit/agent/test_runner.py` |
| P3-9 | Unused `Generic[T]` on CircuitBreaker | DONE | `src/giant/llm/circuit_breaker.py` |
| P3-10 | Confusing `budget_state` naming | DONE | `src/giant/eval/runner.py` |
| P3-11 | Exception chaining inconsistent | DONE | `docs/development/contributing.md`, `src/giant/**` |
| P3-12 | Heuristic provider detection | DONE | `src/giant/llm/protocol.py`, `src/giant/agent/runner.py` |
| P3-13 | Mutates `MessageContent.text` in-place | DONE | `src/giant/agent/context.py` |
| P3-14 | Path validation helpers not centralized | DONE | `src/giant/eval/persistence.py` |
| P3-15 | `run_benchmark` method long | DONE | `src/giant/eval/runner.py` (orchestration delegates) |

---

## Validation Commands (must pass)

- `make format`
- `make lint`
- `make typecheck`
- `uv run pytest tests/unit -x -q`
