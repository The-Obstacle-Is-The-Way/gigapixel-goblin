"""Coordinate transformation utilities for GIANT.

This module re-exports the core coordinate transforms from the WSI layer
and provides additional geometry-aware transformations that operate on
the geometry primitives (Point, Size, Region).

All transforms assume the Level-0 coordinate system as the canonical
"ground truth" for navigation, as specified by the GIANT paper.

Coordinate Systems:
    - Level-0: Highest resolution, absolute pixel coordinates
    - Level-N: Downsampled coordinates at pyramid level N
    - Thumbnail: Coordinates in thumbnail image space

Transform Direction Conventions:
    - level0_to_level: Divide by downsample factor
    - level_to_level0: Multiply by downsample factor
"""

from __future__ import annotations

from giant.geometry.primitives import Point, Region, Size
from giant.wsi.types import (
    level0_to_level,
    level_to_level0,
    size_at_level,
    size_to_level0,
)

# Re-export core transforms from WSI layer
__all__ = [
    "level0_to_level",
    "level_to_level0",
    "point_level0_to_level",
    "point_level_to_level0",
    "region_level0_to_level",
    "region_level_to_level0",
    "size_at_level",
    "size_level0_to_level",
    "size_level_to_level0",
    "size_to_level0",
]


def point_level0_to_level(point: Point, downsample: float) -> Point:
    """Transform a Point from Level-0 to another level.

    Args:
        point: Point in Level-0 coordinates.
        downsample: Downsample factor of the target level.

    Returns:
        Point in the target level's coordinate space.

    Raises:
        ValueError: If downsample is not positive.
    """
    transformed = level0_to_level(point.to_tuple(), downsample)
    return Point(x=transformed[0], y=transformed[1])


def point_level_to_level0(point: Point, downsample: float) -> Point:
    """Transform a Point from a downsampled level to Level-0.

    Args:
        point: Point in downsampled level coordinates.
        downsample: Downsample factor of the source level.

    Returns:
        Point in Level-0 coordinate space.

    Raises:
        ValueError: If downsample is not positive.
    """
    transformed = level_to_level0(point.to_tuple(), downsample)
    return Point(x=transformed[0], y=transformed[1])


def size_level0_to_level(size: Size, downsample: float) -> Size:
    """Transform a Size from Level-0 to another level.

    Args:
        size: Size in Level-0 pixels.
        downsample: Downsample factor of the target level.

    Returns:
        Size in the target level's pixel space.

    Raises:
        ValueError: If downsample is not positive.
    """
    transformed = size_at_level(size.to_tuple(), downsample)
    return Size(width=transformed[0], height=transformed[1])


def size_level_to_level0(size: Size, downsample: float) -> Size:
    """Transform a Size from a downsampled level to Level-0.

    Args:
        size: Size in downsampled level pixels.
        downsample: Downsample factor of the source level.

    Returns:
        Size in Level-0 pixels.

    Raises:
        ValueError: If downsample is not positive.
    """
    transformed = size_to_level0(size.to_tuple(), downsample)
    return Size(width=transformed[0], height=transformed[1])


def region_level0_to_level(region: Region, downsample: float) -> Region:
    """Transform a Region from Level-0 to another level.

    Both the origin and dimensions are transformed. Note that this
    can result in slight rounding differences when round-tripping.

    Args:
        region: Region in Level-0 coordinates.
        downsample: Downsample factor of the target level.

    Returns:
        Region in the target level's coordinate space.

    Raises:
        ValueError: If downsample is not positive.
    """
    origin = level0_to_level((region.x, region.y), downsample)
    dims = size_at_level((region.width, region.height), downsample)
    return Region(
        x=origin[0],
        y=origin[1],
        width=dims[0],
        height=dims[1],
    )


def region_level_to_level0(region: Region, downsample: float) -> Region:
    """Transform a Region from a downsampled level to Level-0.

    Both the origin and dimensions are transformed. Note that this
    can result in slight rounding differences when round-tripping.

    Args:
        region: Region in downsampled level coordinates.
        downsample: Downsample factor of the source level.

    Returns:
        Region in Level-0 coordinate space.

    Raises:
        ValueError: If downsample is not positive.
    """
    origin = level_to_level0((region.x, region.y), downsample)
    dims = size_to_level0((region.width, region.height), downsample)
    return Region(
        x=origin[0],
        y=origin[1],
        width=dims[0],
        height=dims[1],
    )
