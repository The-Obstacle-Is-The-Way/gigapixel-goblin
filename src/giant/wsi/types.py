"""Type definitions for WSI data layer.

Contains data models and protocols for the WSI abstraction layer.
All coordinates follow the OpenSlide convention where Level-0 is the
highest resolution (full magnification).
"""

from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class WSIMetadata:
    """Immutable metadata for a Whole Slide Image.

    This dataclass captures the essential properties of a WSI that are
    needed for navigation and region extraction. All dimension values
    are in pixels.

    Attributes:
        path: Absolute path to the WSI file.
        width: Width of Level-0 (highest resolution) in pixels.
        height: Height of Level-0 (highest resolution) in pixels.
        level_count: Number of pyramid levels available.
        level_dimensions: Tuple of (width, height) for each level.
            Index 0 is Level-0 (highest resolution).
        level_downsamples: Tuple of downsample factors for each level.
            Level-0 always has downsample factor 1.0.
        vendor: Slide scanner vendor (e.g., "aperio", "hamamatsu").
        mpp_x: Microns per pixel in X direction (horizontal).
            None if not available in slide metadata.
        mpp_y: Microns per pixel in Y direction (vertical).
            None if not available in slide metadata.
    """

    path: str
    width: int
    height: int
    level_count: int
    level_dimensions: tuple[tuple[int, int], ...]
    level_downsamples: tuple[float, ...]
    vendor: str
    mpp_x: float | None
    mpp_y: float | None

    @property
    def dimensions(self) -> tuple[int, int]:
        """Return Level-0 dimensions as (width, height)."""
        return (self.width, self.height)

    @property
    def aspect_ratio(self) -> float:
        """Return width/height aspect ratio."""
        return self.width / self.height

    def get_level_dimensions(self, level: int) -> tuple[int, int]:
        """Get dimensions for a specific pyramid level.

        Args:
            level: Pyramid level index (0 = highest resolution).

        Returns:
            (width, height) tuple for the specified level.

        Raises:
            IndexError: If level is out of range.
        """
        if level < 0 or level >= self.level_count:
            raise IndexError(f"Level {level} out of range [0, {self.level_count - 1}]")
        return self.level_dimensions[level]

    def get_downsample(self, level: int) -> float:
        """Get downsample factor for a specific pyramid level.

        Args:
            level: Pyramid level index (0 = highest resolution).

        Returns:
            Downsample factor (1.0 for Level-0).

        Raises:
            IndexError: If level is out of range.
        """
        if level < 0 or level >= self.level_count:
            raise IndexError(f"Level {level} out of range [0, {self.level_count - 1}]")
        return self.level_downsamples[level]


class WSIReaderProtocol(Protocol):
    """Protocol defining the interface for WSI readers.

    This protocol allows for dependency injection and testing with
    mock implementations.
    """

    def get_metadata(self) -> WSIMetadata:
        """Return metadata for the opened WSI.

        Returns:
            WSIMetadata instance with slide properties.
        """
        ...

    def read_region(
        self,
        location: tuple[int, int],
        level: int,
        size: tuple[int, int],
    ) -> Image.Image:
        """Read a region from the WSI.

        Args:
            location: (x, y) tuple of top-left corner in LEVEL-0 coordinates.
            level: Pyramid level to read from (0 = highest resolution).
            size: (width, height) of the region AT THE SPECIFIED LEVEL.

        Returns:
            PIL Image in RGB mode.

        Raises:
            WSIReadError: If the read operation fails.
        """
        ...

    def get_thumbnail(self, max_size: tuple[int, int]) -> Image.Image:
        """Get a thumbnail of the entire slide.

        Args:
            max_size: Maximum (width, height) for the thumbnail.
                The actual thumbnail will maintain aspect ratio.

        Returns:
            PIL Image in RGB mode.

        Raises:
            WSIReadError: If thumbnail generation fails.
        """
        ...

    def close(self) -> None:
        """Close the WSI file and release resources."""
        ...


# Coordinate transformation utilities


def level0_to_level(
    coord: tuple[int, int],
    downsample: float,
) -> tuple[int, int]:
    """Transform Level-0 coordinates to another level.

    Args:
        coord: (x, y) coordinates in Level-0 space.
        downsample: Downsample factor of the target level.

    Returns:
        (x, y) coordinates in the target level's space.
    """
    x, y = coord
    return (int(x / downsample), int(y / downsample))


def level_to_level0(
    coord: tuple[int, int],
    downsample: float,
) -> tuple[int, int]:
    """Transform level coordinates back to Level-0.

    Args:
        coord: (x, y) coordinates in a downsampled level's space.
        downsample: Downsample factor of the source level.

    Returns:
        (x, y) coordinates in Level-0 space.
    """
    x, y = coord
    return (int(x * downsample), int(y * downsample))


def size_at_level(
    size: tuple[int, int],
    downsample: float,
) -> tuple[int, int]:
    """Calculate the size of a region at a specific level.

    Args:
        size: (width, height) in Level-0 pixels.
        downsample: Downsample factor of the target level.

    Returns:
        (width, height) in the target level's pixels.
    """
    w, h = size
    return (max(1, int(w / downsample)), max(1, int(h / downsample)))


def size_to_level0(
    size: tuple[int, int],
    downsample: float,
) -> tuple[int, int]:
    """Calculate the Level-0 size from a level's size.

    Args:
        size: (width, height) in a downsampled level's pixels.
        downsample: Downsample factor of the source level.

    Returns:
        (width, height) in Level-0 pixels.
    """
    w, h = size
    return (int(w * downsample), int(h * downsample))
