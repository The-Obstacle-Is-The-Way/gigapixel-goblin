"""Geometry primitives for GIANT.

This module provides immutable Pydantic models for representing points,
sizes, and regions in Level-0 (absolute pixel) coordinates. All coordinates
follow the convention where (0, 0) is the top-left corner.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class Point(BaseModel, frozen=True):
    """A 2D point in Level-0 pixel coordinates.

    Represents an (x, y) position where x increases rightward and y increases
    downward. Coordinates must be non-negative integers.

    Attributes:
        x: Horizontal position (pixels from left edge).
        y: Vertical position (pixels from top edge).
    """

    x: int = Field(..., ge=0, description="X coordinate (pixels from left)")
    y: int = Field(..., ge=0, description="Y coordinate (pixels from top)")

    def to_tuple(self) -> tuple[int, int]:
        """Convert to (x, y) tuple."""
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, coord: tuple[int, int]) -> Self:
        """Create Point from (x, y) tuple."""
        return cls(x=coord[0], y=coord[1])


class Size(BaseModel, frozen=True):
    """A 2D size representing width and height.

    Both dimensions must be strictly positive (> 0).

    Attributes:
        width: Horizontal extent in pixels.
        height: Vertical extent in pixels.
    """

    width: int = Field(..., gt=0, description="Width in pixels")
    height: int = Field(..., gt=0, description="Height in pixels")

    @property
    def area(self) -> int:
        """Calculate the area in square pixels."""
        return self.width * self.height

    def to_tuple(self) -> tuple[int, int]:
        """Convert to (width, height) tuple."""
        return (self.width, self.height)

    @classmethod
    def from_tuple(cls, size: tuple[int, int]) -> Self:
        """Create Size from (width, height) tuple."""
        return cls(width=size[0], height=size[1])


class Region(BaseModel, frozen=True):
    """A rectangular region in Level-0 coordinates.

    Represents a bounding box defined by top-left corner (x, y) and
    dimensions (width, height). All GIANT navigation occurs in Level-0
    coordinates, making this the canonical representation for crop requests.

    The region is defined as:
    - Top-left: (x, y)
    - Bottom-right: (x + width, y + height) [exclusive]

    Attributes:
        x: Left edge X coordinate (>= 0).
        y: Top edge Y coordinate (>= 0).
        width: Horizontal extent in pixels (> 0).
        height: Vertical extent in pixels (> 0).
    """

    x: int = Field(..., ge=0, description="Left edge X coordinate")
    y: int = Field(..., ge=0, description="Top edge Y coordinate")
    width: int = Field(..., gt=0, description="Width in pixels")
    height: int = Field(..., gt=0, description="Height in pixels")

    @property
    def area(self) -> int:
        """Calculate the area in square pixels."""
        return self.width * self.height

    @property
    def right(self) -> int:
        """Return the X coordinate of the right edge (exclusive)."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Return the Y coordinate of the bottom edge (exclusive)."""
        return self.y + self.height

    @property
    def top_left(self) -> Point:
        """Return the top-left corner as a Point."""
        return Point(x=self.x, y=self.y)

    @property
    def size(self) -> Size:
        """Return the dimensions as a Size."""
        return Size(width=self.width, height=self.height)

    @property
    def center(self) -> tuple[int, int]:
        """Return the center point as (x, y) tuple."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Convert to (x, y, width, height) tuple."""
        return (self.x, self.y, self.width, self.height)

    @classmethod
    def from_tuple(cls, bbox: tuple[int, int, int, int]) -> Self:
        """Create Region from (x, y, width, height) tuple."""
        return cls(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])

    @classmethod
    def from_corners(
        cls,
        top_left: tuple[int, int],
        bottom_right: tuple[int, int],
    ) -> Self:
        """Create Region from corner coordinates.

        Args:
            top_left: (x, y) of top-left corner.
            bottom_right: (x, y) of bottom-right corner (exclusive).

        Returns:
            Region spanning the specified corners.

        Raises:
            ValueError: If bottom_right is not strictly greater than top_left.
        """
        x1, y1 = top_left
        x2, y2 = bottom_right
        width = x2 - x1
        height = y2 - y1
        return cls(x=x1, y=y1, width=width, height=height)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> Self:
        """Ensure width and height remain positive after validation."""
        # Pydantic's gt=0 handles this, but we add explicit check for clarity
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Region dimensions must be positive")
        return self

    def contains_point(self, point: Point) -> bool:
        """Check if a point is inside this region (inclusive of edges).

        Args:
            point: Point to check.

        Returns:
            True if point is within region bounds.
        """
        return self.x <= point.x < self.right and self.y <= point.y < self.bottom

    def intersects(self, other: Region) -> bool:
        """Check if this region overlaps with another.

        Args:
            other: Another Region to check intersection with.

        Returns:
            True if the regions have any overlap.
        """
        return not (
            other.x >= self.right
            or other.right <= self.x
            or other.y >= self.bottom
            or other.bottom <= self.y
        )

    def intersection(self, other: Region) -> Region | None:
        """Compute the intersection of two regions.

        Args:
            other: Another Region to intersect with.

        Returns:
            Region representing the overlap, or None if no intersection.
        """
        if not self.intersects(other):
            return None

        new_x = max(self.x, other.x)
        new_y = max(self.y, other.y)
        new_right = min(self.right, other.right)
        new_bottom = min(self.bottom, other.bottom)

        return Region(
            x=new_x,
            y=new_y,
            width=new_right - new_x,
            height=new_bottom - new_y,
        )
