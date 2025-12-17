# BUG-012: HuggingFace Download Silently Uses No Auth

## Severity: P2 (Medium Priority)

## Status: Open

## Description

The `download_multipathqa_metadata()` function silently proceeds without authentication when `HUGGINGFACE_TOKEN` is not set. For public repos this works, but for private/gated repos it fails with a confusing error.

### Current Code

```python
# src/giant/data/download.py:32-40
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

- Confusing errors for gated datasets
- No feedback about auth status
- Users don't know to set token

### Code Location

- `src/giant/data/download.py:38` - Silent None token

### Testing Required

- Unit test: Verify log message when token is None
- Unit test: Verify token passed when set
