# BUG-032: Placeholder API Keys Treated as Configured (Leads to Repeated 401s)

## Severity: P3 (Developer UX / cost-prevention)

## Status: Fixed

## Summary

`Settings.require_*_key()` treated any non-empty string as a configured secret. If a developer
left a placeholder value (e.g., `"your-key-here"`) in `.env`, GIANT would attempt live API calls
and fail with repeated `401 invalid_api_key` errors instead of failing fast with a clear
configuration error.

## Root Cause

`src/giant/config.py:Settings._is_configured_secret()` only rejected `None` and blank strings.

## Fix

`src/giant/config.py` now rejects obvious placeholder key values (currently: strings containing
`"your-key"` or `"changeme"`), causing `require_*_key()` to raise `ConfigError` before any API
call is attempted.

## Verification

- Extended config unit tests in `tests/unit/test_config.py` to ensure placeholder keys are
  rejected for OpenAI and Anthropic.
