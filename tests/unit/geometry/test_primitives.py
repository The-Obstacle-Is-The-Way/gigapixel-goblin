"""Unit tests for geometry primitives.

Tests Point, Size, and Region Pydantic models including:
- Construction and validation
- Computed properties (area, right, bottom, center)
- Tuple conversion (to/from)
- Region operations (contains_point, intersects, intersection)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from giant.geometry import Point, Region, Size


class TestPoint:
    """Tests for the Point model."""

    def test_point_creation_valid(self) -> None:
        """Test creating a valid Point."""
        point = Point(x=100, y=200)
        assert point.x == 100
        assert point.y == 200

    def test_point_zero_coordinates(self) -> None:
        """Test Point allows zero coordinates."""
        point = Point(x=0, y=0)
        assert point.x == 0
        assert point.y == 0

    def test_point_rejects_negative_x(self) -> None:
        """Test Point rejects negative x coordinate."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Point(x=-1, y=0)

    def test_point_rejects_negative_y(self) -> None:
        """Test Point rejects negative y coordinate."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Point(x=0, y=-1)

    def test_point_to_tuple(self) -> None:
        """Test Point to tuple conversion."""
        point = Point(x=100, y=200)
        assert point.to_tuple() == (100, 200)

    def test_point_from_tuple(self) -> None:
        """Test Point from tuple construction."""
        point = Point.from_tuple((100, 200))
        assert point.x == 100
        assert point.y == 200

    def test_point_is_frozen(self) -> None:
        """Test Point is immutable (frozen)."""
        point = Point(x=100, y=200)
        with pytest.raises(ValidationError):
            point.x = 300  # type: ignore[misc]

    def test_point_equality(self) -> None:
        """Test Point equality comparison."""
        p1 = Point(x=100, y=200)
        p2 = Point(x=100, y=200)
        p3 = Point(x=100, y=300)
        assert p1 == p2
        assert p1 != p3

    def test_point_hashable(self) -> None:
        """Test Point can be used in sets and as dict keys."""
        p1 = Point(x=100, y=200)
        p2 = Point(x=100, y=200)
        points = {p1, p2}
        assert len(points) == 1


class TestSize:
    """Tests for the Size model."""

    def test_size_creation_valid(self) -> None:
        """Test creating a valid Size."""
        size = Size(width=500, height=300)
        assert size.width == 500
        assert size.height == 300

    def test_size_rejects_zero_width(self) -> None:
        """Test Size rejects zero width."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Size(width=0, height=100)

    def test_size_rejects_zero_height(self) -> None:
        """Test Size rejects zero height."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Size(width=100, height=0)

    def test_size_rejects_negative_width(self) -> None:
        """Test Size rejects negative width."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Size(width=-100, height=100)

    def test_size_rejects_negative_height(self) -> None:
        """Test Size rejects negative height."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Size(width=100, height=-100)

    def test_size_area(self) -> None:
        """Test Size area calculation."""
        size = Size(width=100, height=200)
        assert size.area == 20000

    def test_size_area_large(self) -> None:
        """Test Size area with large dimensions (typical WSI)."""
        size = Size(width=100000, height=80000)
        assert size.area == 8_000_000_000

    def test_size_to_tuple(self) -> None:
        """Test Size to tuple conversion."""
        size = Size(width=500, height=300)
        assert size.to_tuple() == (500, 300)

    def test_size_from_tuple(self) -> None:
        """Test Size from tuple construction."""
        size = Size.from_tuple((500, 300))
        assert size.width == 500
        assert size.height == 300

    def test_size_is_frozen(self) -> None:
        """Test Size is immutable (frozen)."""
        size = Size(width=500, height=300)
        with pytest.raises(ValidationError):
            size.width = 600  # type: ignore[misc]


class TestRegion:
    """Tests for the Region model."""

    def test_region_creation_valid(self) -> None:
        """Test creating a valid Region."""
        region = Region(x=100, y=200, width=500, height=300)
        assert region.x == 100
        assert region.y == 200
        assert region.width == 500
        assert region.height == 300

    def test_region_zero_origin(self) -> None:
        """Test Region allows zero origin."""
        region = Region(x=0, y=0, width=100, height=100)
        assert region.x == 0
        assert region.y == 0

    def test_region_rejects_negative_x(self) -> None:
        """Test Region rejects negative x."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Region(x=-1, y=0, width=100, height=100)

    def test_region_rejects_negative_y(self) -> None:
        """Test Region rejects negative y."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Region(x=0, y=-1, width=100, height=100)

    def test_region_rejects_zero_width(self) -> None:
        """Test Region rejects zero width."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Region(x=0, y=0, width=0, height=100)

    def test_region_rejects_zero_height(self) -> None:
        """Test Region rejects zero height."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Region(x=0, y=0, width=100, height=0)

    def test_region_rejects_negative_width(self) -> None:
        """Test Region rejects negative width."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Region(x=0, y=0, width=-100, height=100)

    def test_region_rejects_negative_height(self) -> None:
        """Test Region rejects negative height."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Region(x=0, y=0, width=100, height=-100)

    def test_region_area(self) -> None:
        """Test Region area calculation."""
        region = Region(x=0, y=0, width=100, height=200)
        assert region.area == 20000

    def test_region_right(self) -> None:
        """Test Region right edge calculation."""
        region = Region(x=100, y=0, width=500, height=100)
        assert region.right == 600

    def test_region_bottom(self) -> None:
        """Test Region bottom edge calculation."""
        region = Region(x=0, y=200, width=100, height=300)
        assert region.bottom == 500

    def test_region_top_left(self) -> None:
        """Test Region top_left property."""
        region = Region(x=100, y=200, width=500, height=300)
        top_left = region.top_left
        assert isinstance(top_left, Point)
        assert top_left.x == 100
        assert top_left.y == 200

    def test_region_size(self) -> None:
        """Test Region size property."""
        region = Region(x=100, y=200, width=500, height=300)
        size = region.size
        assert isinstance(size, Size)
        assert size.width == 500
        assert size.height == 300

    def test_region_center(self) -> None:
        """Test Region center calculation."""
        region = Region(x=100, y=200, width=500, height=300)
        center = region.center
        assert center == (350, 350)

    def test_region_center_odd_dimensions(self) -> None:
        """Test Region center with odd dimensions (integer division)."""
        region = Region(x=0, y=0, width=101, height=101)
        center = region.center
        assert center == (50, 50)  # Floor division

    def test_region_to_tuple(self) -> None:
        """Test Region to tuple conversion."""
        region = Region(x=100, y=200, width=500, height=300)
        assert region.to_tuple() == (100, 200, 500, 300)

    def test_region_from_tuple(self) -> None:
        """Test Region from tuple construction."""
        region = Region.from_tuple((100, 200, 500, 300))
        assert region.x == 100
        assert region.y == 200
        assert region.width == 500
        assert region.height == 300

    def test_region_from_corners(self) -> None:
        """Test Region from corner coordinates."""
        region = Region.from_corners(
            top_left=(100, 200),
            bottom_right=(600, 500),
        )
        assert region.x == 100
        assert region.y == 200
        assert region.width == 500
        assert region.height == 300

    def test_region_from_corners_invalid(self) -> None:
        """Test Region from corners rejects invalid corners."""
        with pytest.raises(ValidationError):
            Region.from_corners(
                top_left=(600, 500),
                bottom_right=(100, 200),  # Inverted
            )

    def test_region_is_frozen(self) -> None:
        """Test Region is immutable (frozen)."""
        region = Region(x=100, y=200, width=500, height=300)
        with pytest.raises(ValidationError):
            region.x = 300  # type: ignore[misc]


class TestRegionContainsPoint:
    """Tests for Region.contains_point method."""

    def test_contains_point_inside(self) -> None:
        """Test point inside region."""
        region = Region(x=100, y=100, width=200, height=200)
        point = Point(x=150, y=150)
        assert region.contains_point(point) is True

    def test_contains_point_at_origin(self) -> None:
        """Test point at region origin (inclusive)."""
        region = Region(x=100, y=100, width=200, height=200)
        point = Point(x=100, y=100)
        assert region.contains_point(point) is True

    def test_contains_point_at_bottom_right_edge(self) -> None:
        """Test point at bottom-right edge (exclusive)."""
        region = Region(x=100, y=100, width=200, height=200)
        point = Point(x=300, y=300)  # Right at right/bottom edge
        assert region.contains_point(point) is False

    def test_contains_point_just_inside_right_edge(self) -> None:
        """Test point just inside right edge."""
        region = Region(x=100, y=100, width=200, height=200)
        point = Point(x=299, y=150)
        assert region.contains_point(point) is True

    def test_contains_point_outside_left(self) -> None:
        """Test point outside to the left."""
        region = Region(x=100, y=100, width=200, height=200)
        point = Point(x=50, y=150)
        assert region.contains_point(point) is False

    def test_contains_point_outside_above(self) -> None:
        """Test point outside above."""
        region = Region(x=100, y=100, width=200, height=200)
        point = Point(x=150, y=50)
        assert region.contains_point(point) is False


class TestRegionIntersection:
    """Tests for Region intersection methods."""

    def test_intersects_overlapping(self) -> None:
        """Test intersects returns True for overlapping regions."""
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=50, y=50, width=100, height=100)
        assert r1.intersects(r2) is True
        assert r2.intersects(r1) is True

    def test_intersects_adjacent_no_overlap(self) -> None:
        """Test adjacent regions do not intersect."""
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=100, y=0, width=100, height=100)  # Touching at edge
        assert r1.intersects(r2) is False
        assert r2.intersects(r1) is False

    def test_intersects_contained(self) -> None:
        """Test contained region intersects."""
        outer = Region(x=0, y=0, width=100, height=100)
        inner = Region(x=25, y=25, width=50, height=50)
        assert outer.intersects(inner) is True
        assert inner.intersects(outer) is True

    def test_intersects_disjoint(self) -> None:
        """Test disjoint regions do not intersect."""
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=200, y=200, width=100, height=100)
        assert r1.intersects(r2) is False
        assert r2.intersects(r1) is False

    def test_intersection_overlapping(self) -> None:
        """Test intersection of overlapping regions."""
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=50, y=50, width=100, height=100)
        result = r1.intersection(r2)
        assert result is not None
        assert result.x == 50
        assert result.y == 50
        assert result.width == 50
        assert result.height == 50

    def test_intersection_disjoint(self) -> None:
        """Test intersection of disjoint regions returns None."""
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=200, y=200, width=100, height=100)
        assert r1.intersection(r2) is None

    def test_intersection_contained(self) -> None:
        """Test intersection when one region contains another."""
        outer = Region(x=0, y=0, width=100, height=100)
        inner = Region(x=25, y=25, width=50, height=50)
        result = outer.intersection(inner)
        assert result is not None
        assert result.x == 25
        assert result.y == 25
        assert result.width == 50
        assert result.height == 50

    def test_intersection_symmetric(self) -> None:
        """Test intersection is symmetric."""
        r1 = Region(x=0, y=0, width=100, height=100)
        r2 = Region(x=50, y=50, width=100, height=100)
        assert r1.intersection(r2) == r2.intersection(r1)
