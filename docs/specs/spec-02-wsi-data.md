# Spec-02: WSI Data Layer & OpenSlide Integration

## Overview
This specification defines the data access layer for Whole Slide Images (WSIs). It abstracts the `openslide` library to provide a clean, type-safe interface for querying slide metadata, navigating pyramid levels, and extracting regions (patches) at various resolutions. This layer handles the complexity of coordinate transformations and format compatibility.

## Dependencies
- [Spec-01: Project Foundation & Tooling](./spec-01-foundation.md)

## Acceptance Criteria
- [ ] `WSIReader` class exists and can open standard WSI formats (.svs, .ndpi, .tiff, .mrxs).
- [ ] `WSIReader` correctly reports `dimensions`, `level_count`, `level_dimensions`, and `level_downsamples`.
- [ ] `read_region` method accepts Level-0 coordinates and returns a PIL Image at the specified level.
- [ ] `get_thumbnail` method returns a PIL Image of the full slide at a specified maximum size.
- [ ] Coordinate translation utility correctly maps coordinates between levels.
- [ ] Custom exceptions (`WSIOpenError`, `WSIReadError`) are raised for failure modes.
- [ ] Unit tests use synthetic/mocked OpenSlide objects (avoiding large binary assets in repo).

## Technical Design

### Data Models

```python
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class WSIMetadata:
    path: str
    width: int
    height: int
    level_count: int
    level_dimensions: Tuple[Tuple[int, int], ...]
    level_downsamples: Tuple[float, ...]
    vendor: str
    mpp_x: float | None  # Microns per pixel
    mpp_y: float | None
```

### Interfaces

```python
from typing import Protocol, Tuple
from PIL import Image

class WSIReaderProtocol(Protocol):
    def get_metadata(self) -> WSIMetadata: ...
    def read_region(self, location: Tuple[int, int], level: int, size: Tuple[int, int]) -> Image.Image: ...
    def get_thumbnail(self, max_size: Tuple[int, int]) -> Image.Image: ...
    def close(self) -> None: ...
```

### Implementation Details

#### `WSIReader` Class
Wraps `openslide.OpenSlide`.

- **Initialization:** Takes a file path. Validates file existence and supported extension.
- **Coordinate System:** `openslide.read_region` *always* expects (x, y) in Level-0 (highest resolution) pixel coordinates. The `WSIReader.read_region` wrapper must enforce this and document it clearly.
- **Context Manager:** Should implement `__enter__` and `__exit__` for proper resource cleanup.

#### Error Handling
- `FileNotFoundError`: If path is invalid.
- `openslide.OpenSlideError`: Caught and re-raised as `WSIOpenError` or `WSIReadError` with context.

#### Synthetic Testing
Since WSIs are gigabytes in size, we cannot check them into git.
- **Strategy:** Use `unittest.mock` to mock `openslide.OpenSlide`.
- **Advanced:** Create a small Tiled TIFF using `tifffile` in the test setup to test actual reading logic without 1GB+ files.

## Test Plan

### Unit Tests
1.  **Metadata Extraction:** Mock an OpenSlide object with known dimensions/levels. Verify `get_metadata` returns correct `WSIMetadata`.
2.  **Read Region Passthrough:** Verify `read_region` calls the underlying `openslide.read_region` with correct arguments.
3.  **Error Propagation:** Mock `OpenSlideError` and assert `WSIReadError` is raised.
4.  **Context Manager:** Verify `close()` is called on exit.

### Integration Tests
- **Real File Test:** (Skipped in CI unless a sample file is present) Test opening a small valid `.svs` or `.tiff` if available in a local data directory.

## File Structure

```text
src/giant/wsi/
├── __init__.py
├── reader.py       # WSIReader implementation
├── exceptions.py   # Custom errors
└── types.py        # WSIMetadata and Protocols
tests/unit/wsi/
└── test_reader.py
```

## API Reference

### `WSIReader`

```python
class WSIReader:
    def __init__(self, path: str | Path):
        """Opens a WSI file."""
    
    def read_region(self, location: Tuple[int, int], level: int, size: Tuple[int, int]) -> Image.Image:
        """
        Reads a region from the WSI.
        
        Args:
            location: (x, y) tuple of top-left corner in LEVEL-0 coordinates.
            level: The pyramid level to read from.
            size: (width, height) of the region to read AT THE SPECIFIED LEVEL.
        """
```
