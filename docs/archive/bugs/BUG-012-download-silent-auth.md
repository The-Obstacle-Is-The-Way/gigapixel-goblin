# BUG-012: HuggingFace Download Silently Uses No Auth

## Severity: P3 (Low Priority) - DevEx

## Status: **Fixed**

## Description

`download_multipathqa_metadata()` proceeds without authentication when `HUGGINGFACE_TOKEN` is not set. For public repos this is correct; for private/gated repos it will fail with an auth error from `huggingface_hub`.

### Original Code (Before Fix)

```python
# src/giant/data/download.py (before fix)
def download_multipathqa_metadata(
    output_dir: Path = DEFAULT_MULTIPATHQA_DIR,
    *,
    force: bool = False,
) -> Path:
    csv_path = hf_hub_download(
        repo_id=MULTIPATHQA_REPO_ID,
        filename=MULTIPATHQA_CSV_FILENAME,
        repo_type="dataset",
        local_dir=output_dir,
        force_download=force,
        token=settings.HUGGINGFACE_TOKEN or None,  # No explicit log about auth status
    )
```

### Problems

1. **Silent behavior**: No log message about auth status
2. **Confusing failures**: If the repo becomes gated, users get "401 Unauthorized" with no guidance

### Follow-up Edge Case (Empty Token)

If `.env` contains `HUGGINGFACE_TOKEN=` (empty string), `pydantic-settings` loads it as `""` (not `None`). Passing `token=""` into `hf_hub_download()` can lead to an invalid header like `Authorization: Bearer ` and fail with `httpx.LocalProtocolError: Illegal header value b'Bearer '`.

GIANT treats **blank tokens** as “not set” in this optional-auth path (anonymous access), so an empty token is normalized to `None`.

### Expected Behavior

```python
def download_multipathqa_metadata(...) -> Path:
    token = settings.HUGGINGFACE_TOKEN or None  # Treat empty string as None
    if token is None:
        logger.debug(
            "HUGGINGFACE_TOKEN not set, using anonymous access. "
            "Set token in .env for private/gated datasets."
        )

    csv_path = hf_hub_download(
        ...
        token=token,
    )
```

### Impact

- Minor DevEx: when a dataset becomes gated, users may not realize they need `HUGGINGFACE_TOKEN` until an auth error occurs.
- Prevents confusing `httpx.LocalProtocolError` when token is an empty string.

### Code Location

- `src/giant/data/download.py:28-51` - `download_multipathqa_metadata()` function

### Resolution

Implemented the expected behavior. The function now logs at DEBUG level when no token is set:

```python
# src/giant/data/download.py:28-51 (after fix)
def download_multipathqa_metadata(
    output_dir: Path = DEFAULT_MULTIPATHQA_DIR,
    *,
    force: bool = False,
) -> Path:
    """Download MultiPathQA metadata CSV to the local `data/` directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    token = settings.HUGGINGFACE_TOKEN or None  # Treat empty string as None
    if token is None:
        logger.debug(
            "HUGGINGFACE_TOKEN not set, using anonymous access. "
            "Set token in .env for private/gated datasets."
        )

    csv_path = hf_hub_download(
        repo_id=MULTIPATHQA_REPO_ID,
        filename=MULTIPATHQA_CSV_FILENAME,
        repo_type="dataset",
        local_dir=output_dir,
        force_download=force,
        token=token,
    )
    return Path(csv_path)
```

### Testing

- ✅ Existing download unit tests pass (`tests/unit/test_download.py`)
- Note: The debug-log behavior and empty-token normalization are not explicitly asserted in unit tests today; add a small unit test that captures the `token=` argument passed to `hf_hub_download()` if you want this guaranteed by CI.
