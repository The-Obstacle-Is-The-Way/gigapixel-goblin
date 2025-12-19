# BUG-017: TCGA Downloader Trusts Remote `file_name` for Filesystem Paths

## Severity: P4 (Future) - Security Hardening / Defense-in-Depth

## Status: Fixed (2025-12-19)

## Description

The TCGA downloader writes files using the `file_name` returned by the GDC API:

```python
dest_dir = out_dir / file.file_id
dest_path = dest_dir / file.file_name
```

`file_name` is remote input. If it contains path separators or traversal sequences (e.g. `../`), this could cause writes outside the intended directory.

In practice, the GDC API is expected to return safe basenames, but we should still defensively validate/sanitize the filename since this code is a downloader operating on untrusted network responses.

## Code Location

- `src/giant/data/tcga.py:_download_gdc_file()`

## Expected Behavior

- Reject (or sanitize) any `file_name` that is not a simple basename.
- Prevent absolute paths and any traversal (`..`) regardless of platform.

## Impact

- Low likelihood with a trusted upstream, but high impact if exploited (arbitrary file write within user permissions).

## Proposed Fix

Add a filename validation step:

- Require `Path(file_name).name == file_name`
- Reject absolute paths and any `..` parts

Optionally, sanitize:

- Replace unsafe characters with `_` and store the original name in logs/metadata.

## Testing Required

- Unit test: `file_name="../evil.svs"` raises `ValueError` (or is sanitized to a safe name).

## Resolution

- Added basename/path-traversal validation before writing downloads in `src/giant/data/tcga.py`.
- Verified by `tests/unit/data/test_tcga.py::TestDownloadGdcFileSecurity`.
