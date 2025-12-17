"""WSI Reader implementation wrapping OpenSlide.

This module provides the WSIReader class that abstracts the openslide
library to provide a clean, type-safe interface for WSI operations.
"""

from __future__ import annotations

import ctypes
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import openslide
from PIL import Image

from giant.wsi.exceptions import WSIOpenError, WSIReadError
from giant.wsi.types import WSIMetadata

if TYPE_CHECKING:
    from types import TracebackType

# Supported WSI file extensions (case-insensitive)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".svs",  # Aperio
        ".ndpi",  # Hamamatsu
        ".tiff",  # Generic tiled TIFF
        ".tif",  # Generic tiled TIFF (alternate extension)
        ".mrxs",  # 3DHISTECH MIRAX
        ".vms",  # Hamamatsu VMS
        ".vmu",  # Hamamatsu VMU
        ".scn",  # Leica SCN
        ".bif",  # Ventana BIF
        ".svslide",  # Aperio SVS (alternate)
    }
)


class WSIReader:
    """Reader for Whole Slide Images using OpenSlide.

    This class wraps openslide.OpenSlide to provide a clean, type-safe
    interface with proper error handling and resource management.

    The coordinate system follows OpenSlide conventions:
    - Level 0 is the highest resolution (full magnification)
    - All location parameters are in Level-0 pixel coordinates
    - Size parameters are in the target level's pixel coordinates

    Usage:
        with WSIReader("/path/to/slide.svs") as reader:
            metadata = reader.get_metadata()
            region = reader.read_region((1000, 2000), level=0, size=(512, 512))
            thumb = reader.get_thumbnail((1024, 1024))

    Attributes:
        path: Path to the opened WSI file.
    """

    __slots__ = ("_metadata", "_path", "_slide")

    def __init__(self, path: str | Path) -> None:
        """Open a WSI file.

        Args:
            path: Path to the WSI file.

        Raises:
            WSIOpenError: If the file doesn't exist, has unsupported extension,
                or cannot be opened by OpenSlide.
        """
        self._path = Path(path).resolve()
        self._metadata: WSIMetadata | None = None
        self._slide: openslide.OpenSlide | None

        # Validate file exists
        if not self._path.exists():
            raise WSIOpenError(
                "File not found",
                path=self._path,
            )

        # Validate extension
        suffix = self._path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise WSIOpenError(
                f"Unsupported file extension '{suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                path=self._path,
            )

        # Open with OpenSlide
        try:
            self._slide = openslide.OpenSlide(str(self._path))
        except openslide.OpenSlideError as e:
            raise WSIOpenError(
                f"Failed to open WSI: {e}",
                path=self._path,
            ) from e

    @property
    def path(self) -> Path:
        """Return the path to the WSI file."""
        return self._path

    def _ensure_open(self) -> openslide.OpenSlide:
        slide = self._slide
        if slide is None:
            raise WSIReadError("WSI is closed", path=self._path)
        return slide

    def get_metadata(self) -> WSIMetadata:
        """Get metadata for the opened WSI.

        Returns:
            WSIMetadata instance with slide properties.

        Note:
            Metadata is cached after the first call for efficiency.
        """
        if self._metadata is not None:
            return self._metadata

        slide = self._ensure_open()

        # Extract MPP (microns per pixel) if available
        # Different vendors use different property keys
        props = slide.properties
        mpp_x = self._extract_mpp(props, "openslide.mpp-x")
        mpp_y = self._extract_mpp(props, "openslide.mpp-y")

        # Get vendor from properties
        vendor = props.get("openslide.vendor", "unknown")

        self._metadata = WSIMetadata(
            path=str(self._path),
            width=slide.dimensions[0],
            height=slide.dimensions[1],
            level_count=slide.level_count,
            level_dimensions=tuple(slide.level_dimensions),
            level_downsamples=tuple(slide.level_downsamples),
            vendor=vendor,
            mpp_x=mpp_x,
            mpp_y=mpp_y,
        )
        return self._metadata

    @staticmethod
    def _extract_mpp(
        props: Mapping[str, str],
        key: str,
    ) -> float | None:
        """Extract MPP value from properties, handling various formats.

        Args:
            props: OpenSlide properties mapping.
            key: Property key to extract.

        Returns:
            MPP value as float, or None if not available.
        """
        value = props.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def read_region(
        self,
        location: tuple[int, int],
        level: int,
        size: tuple[int, int],
    ) -> Image.Image:
        """Read a region from the WSI.

        Args:
            location: (x, y) tuple of top-left corner in LEVEL-0 coordinates.
                This is always in the highest resolution coordinate space,
                regardless of which level is being read.
            level: Pyramid level to read from (0 = highest resolution).
            size: (width, height) of the region to read AT THE SPECIFIED LEVEL.
                This is in the target level's pixel coordinates.

        Returns:
            PIL Image in RGB mode (alpha channel removed).

        Raises:
            WSIReadError: If the read operation fails due to invalid
                parameters or OpenSlide errors.

        Example:
            # Read a 512x512 region at level 2, starting at (1000, 2000) in L0 coords
            region = reader.read_region((1000, 2000), level=2, size=(512, 512))
        """
        slide = self._ensure_open()

        # Validate level
        metadata = self.get_metadata()
        if level < 0 or level >= metadata.level_count:
            raise WSIReadError(
                f"Invalid level {level}. "
                f"Must be in range [0, {metadata.level_count - 1}]",
                path=self._path,
                level=level,
                location=location,
                size=size,
            )

        # Validate size is positive
        if size[0] <= 0 or size[1] <= 0:
            raise WSIReadError(
                f"Invalid size {size}. Width and height must be positive.",
                path=self._path,
                level=level,
                location=location,
                size=size,
            )

        # Validate location is non-negative
        if location[0] < 0 or location[1] < 0:
            raise WSIReadError(
                f"Invalid location {location}. Coordinates must be non-negative.",
                path=self._path,
                level=level,
                location=location,
                size=size,
            )

        try:
            # OpenSlide.read_region returns RGBA, convert to RGB
            rgba_image = slide.read_region(location, level, size)
            return rgba_image.convert("RGB")
        except (openslide.OpenSlideError, ctypes.ArgumentError) as e:
            raise WSIReadError(
                f"Failed to read region: {e}",
                path=self._path,
                level=level,
                location=location,
                size=size,
            ) from e
        except Exception as e:
            raise WSIReadError(
                f"Failed to read region: {e}",
                path=self._path,
                level=level,
                location=location,
                size=size,
            ) from e

    def get_thumbnail(self, max_size: tuple[int, int]) -> Image.Image:
        """Get a thumbnail of the entire slide.

        The thumbnail maintains the slide's aspect ratio and fits within
        the specified maximum dimensions.

        Args:
            max_size: Maximum (width, height) for the thumbnail.

        Returns:
            PIL Image in RGB mode.

        Raises:
            WSIReadError: If thumbnail generation fails.
        """
        slide = self._ensure_open()

        if max_size[0] <= 0 or max_size[1] <= 0:
            raise WSIReadError(
                f"Invalid max_size {max_size}. Dimensions must be positive.",
                path=self._path,
            )

        try:
            # OpenSlide.get_thumbnail returns RGBA, convert to RGB
            thumbnail = slide.get_thumbnail(max_size)
            return thumbnail.convert("RGB")
        except Exception as e:
            raise WSIReadError(
                f"Failed to generate thumbnail: {e}",
                path=self._path,
            ) from e

    def get_best_level_for_downsample(self, downsample: float) -> int:
        """Get the best pyramid level for a given downsample factor.

        This is useful for selecting an appropriate level when you know
        the desired downsampling but not the specific level index.

        Args:
            downsample: Desired downsample factor (1.0 = Level-0).

        Returns:
            Best matching level index.

        Note:
            Delegates to OpenSlide which handles edge cases internally.
            For values <= 0, OpenSlide returns level 0.
        """
        slide = self._ensure_open()
        try:
            return slide.get_best_level_for_downsample(downsample)
        except Exception as e:
            raise WSIReadError(
                f"Failed to get best level for downsample: {e}",
                path=self._path,
            ) from e

    def close(self) -> None:
        """Close the WSI file and release resources.

        After calling close(), the reader should not be used.
        It's recommended to use the context manager pattern instead.
        """
        if self._slide is None:
            return
        self._slide.close()
        self._slide = None

    def __enter__(self) -> WSIReader:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager and close the slide."""
        self.close()

    def __repr__(self) -> str:
        """Return string representation."""
        return f"WSIReader(path={self._path!r})"
