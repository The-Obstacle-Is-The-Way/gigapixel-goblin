# BUG-035: CLI Exceptions May Leak API Keys in Tracebacks

## Severity: P1 (Security / secret leakage)

## Status: Proposed Fix Spec (Not Implemented)

## Summary

When the CLI crashes (e.g., misconfiguration, missing API key, invalid args), Typer/Rich pretty tracebacks can include **locals**, which may contain `Settings` objects and therefore API keys. This is especially risky when users paste logs into issues or share terminal output.

## Repro

1. Ensure at least one provider key is configured (e.g., `ANTHROPIC_API_KEY`).
2. Trigger a CLI error (e.g., run a command that raises `ConfigError` for a different missing key).
3. Observe that the traceback may print local variables and include the configured key value.

## Root Cause

- Typer’s Rich exception formatting can show locals by default.
- `giant.config.Settings` stores secrets as plain `str | None`, so printing locals can expose them.

## Proposed Fix

1. **Disable locals in pretty exceptions**
   - In `src/giant/cli/main.py`, set Typer options:
     - `pretty_exceptions_show_locals=False`
     - Optionally `pretty_exceptions_short=True`

2. **Defense-in-depth: mask secrets in `Settings`**
   - Consider switching key fields to `pydantic.SecretStr` (requires updating `require_*_key()` call sites to use `.get_secret_value()`).
   - Alternatively, keep string types but ensure any custom logging never prints key values.

3. **Regression test**
   - Add a CLI test that:
     - Sets an environment variable like `ANTHROPIC_API_KEY="sk-ant-TESTSECRET"`.
     - Runs a CLI command expected to error.
     - Asserts the output does **not** contain `TESTSECRET`.

## Acceptance Criteria

- CLI errors never print API key material (even when `-vv` is used).
- Logs and tracebacks remain actionable without showing locals that include secrets.
