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
        token=settings.HUGGINGFACE_TOKEN or None,  # ← Silently None
    )
```

### Problems

1. **Redundant code**: `settings.HUGGINGFACE_TOKEN or None` - the token is already `None` if not set
2. **Silent behavior**: No log message about auth status
3. **Confusing failures**: If the repo becomes gated, users get "401 Unauthorized" with no guidance

### Expected Behavior

```python
def download_multipathqa_metadata(...) -> Path:
    token = settings.HUGGINGFACE_TOKEN
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

    token = settings.HUGGINGFACE_TOKEN
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

- ✅ Existing download unit tests pass
- ✅ Debug log emitted when token is None
