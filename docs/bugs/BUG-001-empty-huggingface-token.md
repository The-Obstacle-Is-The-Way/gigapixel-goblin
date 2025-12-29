# BUG-001: Empty HUGGINGFACE_TOKEN causes download failure

## Summary
When `HUGGINGFACE_TOKEN=` is set to an empty string in `.env`, the `giant download multipathqa` command fails with `httpx.LocalProtocolError: Illegal header value b'Bearer '`.

## Root Cause
In `src/giant/data/download.py:36-41`, the token validation only checks for `None`:

```python
token = settings.HUGGINGFACE_TOKEN
if token is None:
    logger.debug("HUGGINGFACE_TOKEN not set...")
```

When the env var is set but empty (`HUGGINGFACE_TOKEN=`), `settings.HUGGINGFACE_TOKEN` returns `""` (empty string), which passes the `is None` check. This empty string is then passed to `hf_hub_download(token="")`, which constructs an invalid `Authorization: Bearer ` header (with nothing after "Bearer ").

## Impact
- Users cannot download MultiPathQA metadata if they have an empty HUGGINGFACE_TOKEN in their .env
- Confusing error message doesn't indicate the actual problem

## Fix Applied
Changed validation to treat empty strings as equivalent to None:

```python
token = settings.HUGGINGFACE_TOKEN or None  # Treat empty string as None
```

## Workaround (if fix not applied)
1. Remove or comment out the `HUGGINGFACE_TOKEN=` line from `.env`, OR
2. Download manually: `curl -L "https://huggingface.co/datasets/tbuckley/MultiPathQA/resolve/main/MultiPathQA.csv" -o data/multipathqa/MultiPathQA.csv`

## Context: Why This Was Discovered

**Note:** The MultiPathQA CSV is already committed to git (added in PR #20). The `giant download multipathqa` command is only needed if the CSV is missing or for fresh clones.

The existing benchmarks (GTEx, TCGA) ran successfully on 2025-12-27 without hitting this bug because they used the already-committed CSV file.

This bug was discovered when attempting to run PANDA benchmark and mistakenly thinking the CSV was missing.

## Status
**Fixed** - `src/giant/data/download.py` updated
