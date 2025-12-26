# BUG-034: Default Test Targets Can Trigger Live API Calls

## Severity: P0 (Cost + accidental network calls)

## Status: Proposed Fix Spec (Not Implemented)

## Summary

`make test` (and therefore `make check`) runs `uv run pytest` without excluding `live`/`cost` tests. If a developer has `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` configured (shell env or `.env`), pytest will run marked live tests and spend money.

## Repro

```bash
# With real keys configured
make test
```

## Root Cause

- Live tests in `tests/integration/llm/test_p0_critical.py` are only gated by “key is present”, not by an explicit opt-in flag.
- Make targets do not exclude `live`/`cost` markers.

## Proposed Fix

1. **Safe defaults in Makefile**
   - Update these targets to exclude live/cost by default:
     - `test`: `uv run pytest -m "not live and not cost"`
     - `test-cov`: same marker exclusion plus coverage flags
     - `test-watch`: same marker exclusion

2. **Explicit opt-in targets**
   - Add targets that *intentionally* run live tests:
     - `test-live`: `uv run pytest -m "live"`
     - Optionally split by provider: `test-live-openai`, `test-live-anthropic`
   - Document these in `AGENTS.md` and/or `README.md`.

3. **Defense-in-depth: require an explicit env opt-in**
   - Update live test `skipif` gates to require **both** a configured key and an explicit environment variable, e.g. `GIANT_RUN_LIVE_TESTS=1`.
   - Keep `-m live` as a second explicit opt-in (marker selection).

## Acceptance Criteria

- With keys configured, `make test` and `make check` do not run any `live` or `cost` tests.
- Live tests only run when explicitly requested (e.g., `GIANT_RUN_LIVE_TESTS=1 uv run pytest -m live`).

## Test Plan

- Unit: add a small test for `_has_openai_key()`-style gating (or refactor to a shared helper) verifying that keys alone are insufficient without `GIANT_RUN_LIVE_TESTS=1`.
- Manual: set a dummy key in `.env`, run `make test` and confirm no network calls occur.
