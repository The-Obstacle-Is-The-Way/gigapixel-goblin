# Technical Debt: P1-2 BenchmarkRunner Refactor (COMPLETED)

**Priority:** P1 (High)
**Effort:** Large (2-4 days)
**Risk:** LOW for correctness, MEDIUM for maintainability
**Status:** ✅ COMPLETED (implemented)
**Last Verified:** 2026-01-01

---

## Summary

`src/giant/eval/runner.py` previously contained a ~1000-line `BenchmarkRunner`
that mixed:
- CSV parsing and item construction
- WSI path resolution
- Per-item execution for multiple modes
- Majority voting / scoring glue
- Filesystem persistence (results + trajectories)
- Orchestration, concurrency, checkpointing, and metrics

This violated SRP and made the evaluation subsystem hard to modify safely.

---

## Implemented Architecture (2026-01-01)

Responsibilities are now separated into focused modules:

```
src/giant/eval/
├── runner.py        # EvaluationOrchestrator + EvaluationConfig/Results (orchestration)
├── loader.py        # BenchmarkItemLoader (CSV parsing + item construction)
├── executor.py      # ItemExecutor (mode execution + voting)
├── persistence.py   # ResultsPersistence (results + trajectory writes; path safety helpers)
├── wsi_resolver.py  # WSIPathResolver (path resolution)
└── metrics.py       # Metric implementations (accuracy, bootstrap, etc.)
```

Current file sizes:
- `src/giant/eval/runner.py`: 403 lines
- `src/giant/eval/loader.py`: 262 lines
- `src/giant/eval/executor.py`: 336 lines
- `src/giant/eval/persistence.py`: 79 lines

---

## API Compatibility

Backwards-compatible import preserved:

```python
from giant.eval.runner import BenchmarkRunner, EvaluationConfig
```

Preferred name (same implementation):

```python
from giant.eval.runner import EvaluationOrchestrator, EvaluationConfig
```

`BenchmarkRunner` is an alias of `EvaluationOrchestrator`.

---

## Notes / What This Closed

- P1-2 SRP violation: `BenchmarkRunner` split into loader/executor/persistence.
- P3-14 path helper consolidation: `ResultsPersistence.validate_run_id()` and
  `ResultsPersistence.safe_filename_component()` are now the canonical helpers.
- P3-15 long `run_benchmark`: shortened by delegating work to composed
  components.

---

## Validation Commands (must pass)

- `make format`
- `make lint`
- `make typecheck`
- `uv run pytest tests/unit -x -q`
