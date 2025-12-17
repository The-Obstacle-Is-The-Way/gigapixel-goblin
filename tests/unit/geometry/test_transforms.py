"""Unit tests for geometry coordinate transforms.

Tests the geometry-aware transform functions that operate on
Point, Size, and Region primitives.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from giant.geometry import Point, Region, Size
from giant.geometry.transforms import (
    level0_to_level,
    level_to_level0,
    point_level0_to_level,
    point_level_to_level0,
    region_level0_to_level,
    region_level_to_level0,
    size_at_level,
    size_level0_to_level,
    size_level_to_level0,
    size_to_level0,
)


class TestReExportedTransforms:
    """Tests for re-exported tuple-based transforms."""

    def test_level0_to_level_re_exported(self) -> None:
        """Test level0_to_level is properly re-exported."""
        result = level0_to_level((1000, 2000), 4.0)
        assert result == (250, 500)

    def test_level_to_level0_re_exported(self) -> None:
        """Test level_to_level0 is properly re-exported."""
        result = level_to_level0((250, 500), 4.0)
        assert result == (1000, 2000)

    def test_size_at_level_re_exported(self) -> None:
        """Test size_at_level is properly re-exported."""
        result = size_at_level((1000, 800), 4.0)
        assert result == (250, 200)

    def test_size_to_level0_re_exported(self) -> None:
        """Test size_to_level0 is properly re-exported."""
        result = size_to_level0((250, 200), 4.0)
        assert result == (1000, 800)


class TestPointTransforms:
    """Tests for Point-based coordinate transforms."""

    def test_point_level0_to_level_basic(self) -> None:
        """Test basic Point L0 to level transform."""
        point = Point(x=1000, y=2000)
        result = point_level0_to_level(point, downsample=4.0)
        assert isinstance(result, Point)
        assert result.x == 250
        assert result.y == 500

    def test_point_level0_to_level_unit_downsample(self) -> None:
        """Test Point transform with downsample=1 (no change)."""
        point = Point(x=1000, y=2000)
        result = point_level0_to_level(point, downsample=1.0)
        assert result.x == 1000
        assert result.y == 2000

    def test_point_level0_to_level_large_downsample(self) -> None:
        """Test Point transform with large downsample."""
        point = Point(x=100000, y=80000)
        result = point_level0_to_level(point, downsample=32.0)
        assert result.x == 3125
        assert result.y == 2500

    def test_point_level0_to_level_fractional_downsample(self) -> None:
        """Test Point transform with fractional downsample."""
        point = Point(x=1000, y=2000)
        result = point_level0_to_level(point, downsample=2.5)
        assert result.x == 400
        assert result.y == 800

    def test_point_level_to_level0_basic(self) -> None:
        """Test basic Point level to L0 transform."""
        point = Point(x=250, y=500)
        result = point_level_to_level0(point, downsample=4.0)
        assert isinstance(result, Point)
        assert result.x == 1000
        assert result.y == 2000

    def test_point_level_to_level0_unit_downsample(self) -> None:
        """Test Point transform with downsample=1 (no change)."""
        point = Point(x=1000, y=2000)
        result = point_level_to_level0(point, downsample=1.0)
        assert result.x == 1000
        assert result.y == 2000

    def test_point_transform_rejects_zero_downsample(self) -> None:
        """Test Point transform rejects zero downsample."""
        point = Point(x=100, y=200)
        with pytest.raises(ValueError, match="must be positive"):
            point_level0_to_level(point, downsample=0.0)

    def test_point_transform_rejects_negative_downsample(self) -> None:
        """Test Point transform rejects negative downsample."""
        point = Point(x=100, y=200)
        with pytest.raises(ValueError, match="must be positive"):
            point_level_to_level0(point, downsample=-1.0)


class TestSizeTransforms:
    """Tests for Size-based coordinate transforms."""

    def test_size_level0_to_level_basic(self) -> None:
        """Test basic Size L0 to level transform."""
        size = Size(width=1000, height=800)
        result = size_level0_to_level(size, downsample=4.0)
        assert isinstance(result, Size)
        assert result.width == 250
        assert result.height == 200

    def test_size_level0_to_level_ensures_minimum(self) -> None:
        """Test Size transform ensures minimum 1px."""
        size = Size(width=2, height=2)
        result = size_level0_to_level(size, downsample=4.0)
        # 2/4 = 0.5, but should be at least 1
        assert result.width >= 1
        assert result.height >= 1

    def test_size_level_to_level0_basic(self) -> None:
        """Test basic Size level to L0 transform."""
        size = Size(width=250, height=200)
        result = size_level_to_level0(size, downsample=4.0)
        assert isinstance(result, Size)
        assert result.width == 1000
        assert result.height == 800

    def test_size_transform_rejects_zero_downsample(self) -> None:
        """Test Size transform rejects zero downsample."""
        size = Size(width=100, height=100)
        with pytest.raises(ValueError, match="must be positive"):
            size_level0_to_level(size, downsample=0.0)

    def test_size_transform_rejects_negative_downsample(self) -> None:
        """Test Size transform rejects negative downsample."""
        size = Size(width=100, height=100)
        with pytest.raises(ValueError, match="must be positive"):
            size_level_to_level0(size, downsample=-1.0)


class TestRegionTransforms:
    """Tests for Region-based coordinate transforms."""

    def test_region_level0_to_level_basic(self) -> None:
        """Test basic Region L0 to level transform."""
        region = Region(x=1000, y=2000, width=4000, height=3200)
        result = region_level0_to_level(region, downsample=4.0)
        assert isinstance(result, Region)
        assert result.x == 250
        assert result.y == 500
        assert result.width == 1000
        assert result.height == 800

    def test_region_level0_to_level_unit_downsample(self) -> None:
        """Test Region transform with downsample=1 (no change)."""
        region = Region(x=1000, y=2000, width=500, height=400)
        result = region_level0_to_level(region, downsample=1.0)
        assert result.x == 1000
        assert result.y == 2000
        assert result.width == 500
        assert result.height == 400

    def test_region_level_to_level0_basic(self) -> None:
        """Test basic Region level to L0 transform."""
        region = Region(x=250, y=500, width=1000, height=800)
        result = region_level_to_level0(region, downsample=4.0)
        assert isinstance(result, Region)
        assert result.x == 1000
        assert result.y == 2000
        assert result.width == 4000
        assert result.height == 3200

    def test_region_transform_rejects_zero_downsample(self) -> None:
        """Test Region transform rejects zero downsample."""
        region = Region(x=0, y=0, width=100, height=100)
        with pytest.raises(ValueError, match="must be positive"):
            region_level0_to_level(region, downsample=0.0)

    def test_region_transform_rejects_negative_downsample(self) -> None:
        """Test Region transform rejects negative downsample."""
        region = Region(x=0, y=0, width=100, height=100)
        with pytest.raises(ValueError, match="must be positive"):
            region_level_to_level0(region, downsample=-1.0)


class TestTransformRoundtrips:
    """Property-based tests for transform roundtrips."""

    @given(
        x=st.integers(min_value=0, max_value=100000),
        y=st.integers(min_value=0, max_value=100000),
        downsample=st.floats(min_value=1.0, max_value=64.0),
    )
    def test_point_roundtrip_approximate(
        self, x: int, y: int, downsample: float
    ) -> None:
        """Test Point L0 -> LN -> L0 roundtrip within rounding error.

        Due to integer truncation in both forward and backward transforms,
        the error bound is 2*downsample (worst case: loses d-1 in each direction).
        """
        original = Point(x=x, y=y)
        transformed = point_level0_to_level(original, downsample)
        roundtripped = point_level_to_level0(transformed, downsample)

        # Error bound accounts for truncation in both directions
        error_bound = 2 * downsample
        assert abs(roundtripped.x - original.x) < error_bound
        assert abs(roundtripped.y - original.y) < error_bound

    @given(
        width=st.integers(min_value=1, max_value=10000),
        height=st.integers(min_value=1, max_value=10000),
        downsample=st.floats(min_value=1.0, max_value=64.0),
    )
    def test_size_roundtrip_approximate(
        self, width: int, height: int, downsample: float
    ) -> None:
        """Test Size L0 -> LN -> L0 roundtrip within rounding error.

        Due to integer truncation in both forward and backward transforms,
        the error bound is 2*downsample.
        """
        original = Size(width=width, height=height)
        transformed = size_level0_to_level(original, downsample)
        roundtripped = size_level_to_level0(transformed, downsample)

        # Error bound accounts for truncation in both directions
        error_bound = 2 * downsample
        assert abs(roundtripped.width - original.width) < error_bound
        assert abs(roundtripped.height - original.height) < error_bound

    @given(
        x=st.integers(min_value=0, max_value=50000),
        y=st.integers(min_value=0, max_value=50000),
        width=st.integers(min_value=1, max_value=5000),
        height=st.integers(min_value=1, max_value=5000),
        downsample=st.floats(min_value=1.0, max_value=32.0),
    )
    def test_region_roundtrip_approximate(
        self, x: int, y: int, width: int, height: int, downsample: float
    ) -> None:
        """Test Region L0 -> LN -> L0 roundtrip within rounding error.

        Due to integer truncation in both forward and backward transforms,
        the error bound is 2*downsample.
        """
        original = Region(x=x, y=y, width=width, height=height)
        transformed = region_level0_to_level(original, downsample)
        roundtripped = region_level_to_level0(transformed, downsample)

        # Error bound accounts for truncation in both directions
        error_bound = 2 * downsample
        assert abs(roundtripped.x - original.x) < error_bound
        assert abs(roundtripped.y - original.y) < error_bound
        assert abs(roundtripped.width - original.width) < error_bound
        assert abs(roundtripped.height - original.height) < error_bound


class TestTransformEdgeCases:
    """Tests for transform edge cases."""

    def test_point_at_origin_transforms_correctly(self) -> None:
        """Test Point at origin transforms without issues."""
        point = Point(x=0, y=0)
        result = point_level0_to_level(point, downsample=4.0)
        assert result.x == 0
        assert result.y == 0

    def test_region_at_origin_transforms_correctly(self) -> None:
        """Test Region at origin transforms without issues."""
        region = Region(x=0, y=0, width=100, height=100)
        result = region_level0_to_level(region, downsample=4.0)
        assert result.x == 0
        assert result.y == 0

    def test_small_region_at_high_downsample(self) -> None:
        """Test small region at high downsample maintains minimum size."""
        region = Region(x=0, y=0, width=10, height=10)
        result = region_level0_to_level(region, downsample=32.0)
        # 10/32 = 0.3125, but should be at least 1
        assert result.width >= 1
        assert result.height >= 1

    def test_typical_wsi_dimensions(self) -> None:
        """Test transforms work with typical WSI dimensions."""
        # Typical Aperio slide dimensions
        region = Region(x=50000, y=40000, width=10000, height=8000)
        result = region_level0_to_level(region, downsample=16.0)
        assert result.x == 3125
        assert result.y == 2500
        assert result.width == 625
        assert result.height == 500
