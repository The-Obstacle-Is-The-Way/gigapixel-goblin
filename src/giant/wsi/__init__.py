"""WSI Data Layer for GIANT.

This package provides abstractions for working with Whole Slide Images (WSIs)
through the OpenSlide library. It offers a clean, type-safe interface for
querying metadata, navigating pyramid levels, and extracting regions.

Key Components:
    - WSIReader: Main class for opening and reading WSI files
    - WSIMetadata: Immutable dataclass for slide properties
    - WSIReaderProtocol: Protocol for dependency injection
    - Coordinate transforms: Utilities for Level-0 <-> Level-N conversions

Example:
    from giant.wsi import WSIReader

    with WSIReader("slide.svs") as reader:
        metadata = reader.get_metadata()
        print(f"Slide size: {metadata.width}x{metadata.height}")

        # Read a region at Level 0
        region = reader.read_region((1000, 2000), level=0, size=(512, 512))

        # Get thumbnail for overview
        thumb = reader.get_thumbnail((1024, 1024))
"""

from giant.wsi.exceptions import WSIError, WSIOpenError, WSIReadError
from giant.wsi.reader import SUPPORTED_EXTENSIONS, WSIReader
from giant.wsi.types import (
    WSIMetadata,
    WSIReaderProtocol,
    level0_to_level,
    level_to_level0,
    size_at_level,
    size_to_level0,
)

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "WSIError",
    "WSIMetadata",
    "WSIOpenError",
    "WSIReadError",
    "WSIReader",
    "WSIReaderProtocol",
    "level0_to_level",
    "level_to_level0",
    "size_at_level",
    "size_to_level0",
]
