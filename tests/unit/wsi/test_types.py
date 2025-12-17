"""Unit tests for WSI type definitions and coordinate transforms."""

from __future__ import annotations

import pytest

from giant.wsi.types import (
    WSIMetadata,
    level0_to_level,
    level_to_level0,
    size_at_level,
    size_to_level0,
)


class TestWSIMetadata:
    """Tests for WSIMetadata dataclass."""

    @pytest.fixture
    def sample_metadata(self) -> WSIMetadata:
        """Create a sample WSIMetadata for testing."""
        return WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=50000,
            level_count=4,
            level_dimensions=(
                (100000, 50000),  # Level 0
                (25000, 12500),  # Level 1 (4x downsample)
                (6250, 3125),  # Level 2 (16x downsample)
                (1562, 781),  # Level 3 (64x downsample)
            ),
            level_downsamples=(1.0, 4.0, 16.0, 64.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )

    def test_dimensions_property(self, sample_metadata: WSIMetadata) -> None:
        """Test dimensions property returns (width, height) tuple."""
        assert sample_metadata.dimensions == (100000, 50000)

    def test_aspect_ratio_property(self, sample_metadata: WSIMetadata) -> None:
        """Test aspect ratio calculation."""
        assert sample_metadata.aspect_ratio == 2.0

    def test_get_level_dimensions_valid(self, sample_metadata: WSIMetadata) -> None:
        """Test getting dimensions for valid levels."""
        assert sample_metadata.get_level_dimensions(0) == (100000, 50000)
        assert sample_metadata.get_level_dimensions(1) == (25000, 12500)
        assert sample_metadata.get_level_dimensions(2) == (6250, 3125)
        assert sample_metadata.get_level_dimensions(3) == (1562, 781)

    def test_get_level_dimensions_out_of_range(
        self, sample_metadata: WSIMetadata
    ) -> None:
        """Test IndexError for invalid level."""
        with pytest.raises(IndexError, match=r"Level 4 out of range"):
            sample_metadata.get_level_dimensions(4)

        with pytest.raises(IndexError, match=r"Level -1 out of range"):
            sample_metadata.get_level_dimensions(-1)

    def test_get_downsample_valid(self, sample_metadata: WSIMetadata) -> None:
        """Test getting downsample factors for valid levels."""
        assert sample_metadata.get_downsample(0) == 1.0
        assert sample_metadata.get_downsample(1) == 4.0
        assert sample_metadata.get_downsample(2) == 16.0
        assert sample_metadata.get_downsample(3) == 64.0

    def test_get_downsample_out_of_range(self, sample_metadata: WSIMetadata) -> None:
        """Test IndexError for invalid level."""
        with pytest.raises(IndexError, match=r"Level 5 out of range"):
            sample_metadata.get_downsample(5)

    def test_metadata_is_frozen(self, sample_metadata: WSIMetadata) -> None:
        """Test that metadata is immutable."""
        with pytest.raises(AttributeError):
            sample_metadata.width = 200000  # type: ignore[misc]

    def test_metadata_with_none_mpp(self) -> None:
        """Test metadata can be created with None MPP values."""
        metadata = WSIMetadata(
            path="/path/to/slide.ndpi",
            width=50000,
            height=50000,
            level_count=3,
            level_dimensions=((50000, 50000), (12500, 12500), (3125, 3125)),
            level_downsamples=(1.0, 4.0, 16.0),
            vendor="hamamatsu",
            mpp_x=None,
            mpp_y=None,
        )
        assert metadata.mpp_x is None
        assert metadata.mpp_y is None


class TestCoordinateTransforms:
    """Tests for coordinate transformation utilities."""

    def test_level0_to_level_basic(self) -> None:
        """Test basic Level-0 to Level-N transformation."""
        # At 4x downsample, (1000, 2000) becomes (250, 500)
        result = level0_to_level((1000, 2000), downsample=4.0)
        assert result == (250, 500)

    def test_level0_to_level_no_downsample(self) -> None:
        """Test transformation with 1.0 downsample (identity)."""
        result = level0_to_level((1000, 2000), downsample=1.0)
        assert result == (1000, 2000)

    def test_level0_to_level_high_downsample(self) -> None:
        """Test transformation with high downsample factor."""
        result = level0_to_level((64000, 32000), downsample=64.0)
        assert result == (1000, 500)

    def test_level0_to_level_fractional(self) -> None:
        """Test transformation handles non-integer results."""
        # (100, 100) at 3x downsample = (33, 33) (truncated)
        result = level0_to_level((100, 100), downsample=3.0)
        assert result == (33, 33)

    def test_level_to_level0_basic(self) -> None:
        """Test basic Level-N to Level-0 transformation."""
        # At 4x downsample, (250, 500) becomes (1000, 2000)
        result = level_to_level0((250, 500), downsample=4.0)
        assert result == (1000, 2000)

    def test_level_to_level0_no_downsample(self) -> None:
        """Test transformation with 1.0 downsample (identity)."""
        result = level_to_level0((1000, 2000), downsample=1.0)
        assert result == (1000, 2000)

    def test_roundtrip_coordinate_transform(self) -> None:
        """Test that transforming to level and back returns original."""
        original = (12345, 67890)
        downsample = 4.0

        at_level = level0_to_level(original, downsample)
        back_to_l0 = level_to_level0(at_level, downsample)

        # Due to integer truncation, we may lose precision
        # The result should be within 1 downsample unit of original
        assert abs(back_to_l0[0] - original[0]) < downsample
        assert abs(back_to_l0[1] - original[1]) < downsample

    def test_size_at_level_basic(self) -> None:
        """Test size transformation to different level."""
        # A 1000x500 region at L0 becomes 250x125 at 4x downsample
        result = size_at_level((1000, 500), downsample=4.0)
        assert result == (250, 125)

    def test_size_at_level_minimum_one(self) -> None:
        """Test that size never goes below 1."""
        # A 10x10 region at 64x downsample should be (1, 1), not (0, 0)
        result = size_at_level((10, 10), downsample=64.0)
        assert result == (1, 1)

    def test_size_to_level0_basic(self) -> None:
        """Test size transformation back to Level-0."""
        # A 250x125 region at 4x becomes 1000x500 at L0
        result = size_to_level0((250, 125), downsample=4.0)
        assert result == (1000, 500)


class TestCoordinateTransformEdgeCases:
    """Edge case tests for coordinate transforms."""

    def test_zero_coordinates(self) -> None:
        """Test handling of zero coordinates."""
        assert level0_to_level((0, 0), downsample=4.0) == (0, 0)
        assert level_to_level0((0, 0), downsample=4.0) == (0, 0)

    def test_large_coordinates(self) -> None:
        """Test handling of large coordinates (gigapixel scale)."""
        large_coord = (1_000_000_000, 500_000_000)  # 1 billion x 500 million
        result = level0_to_level(large_coord, downsample=1000.0)
        assert result == (1_000_000, 500_000)

    def test_very_small_downsample(self) -> None:
        """Test with downsample factor less than 1 (upsampling)."""
        # This is unusual but should work mathematically
        result = level0_to_level((100, 100), downsample=0.5)
        assert result == (200, 200)

    def test_non_power_of_two_downsample(self) -> None:
        """Test with non-standard downsample factors."""
        # Some slides have non-power-of-2 downsamples like 3.999...
        result = level0_to_level((1000, 1000), downsample=3.99)
        assert result == (250, 250)


class TestDownsampleValidation:
    """Tests for downsample factor validation in transform utilities."""

    def test_level0_to_level_rejects_zero_downsample(self) -> None:
        """Test that level0_to_level raises ValueError for zero downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got 0"):
            level0_to_level((100, 100), downsample=0.0)

    def test_level0_to_level_rejects_negative_downsample(self) -> None:
        """Test that level0_to_level raises ValueError for negative downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got -1"):
            level0_to_level((100, 100), downsample=-1.0)

    def test_level_to_level0_rejects_zero_downsample(self) -> None:
        """Test that level_to_level0 raises ValueError for zero downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got 0"):
            level_to_level0((100, 100), downsample=0.0)

    def test_level_to_level0_rejects_negative_downsample(self) -> None:
        """Test that level_to_level0 raises ValueError for negative downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got -2"):
            level_to_level0((100, 100), downsample=-2.0)

    def test_size_at_level_rejects_zero_downsample(self) -> None:
        """Test that size_at_level raises ValueError for zero downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got 0"):
            size_at_level((100, 100), downsample=0.0)

    def test_size_at_level_rejects_negative_downsample(self) -> None:
        """Test that size_at_level raises ValueError for negative downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got -0.5"):
            size_at_level((100, 100), downsample=-0.5)

    def test_size_to_level0_rejects_zero_downsample(self) -> None:
        """Test that size_to_level0 raises ValueError for zero downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got 0"):
            size_to_level0((100, 100), downsample=0.0)

    def test_size_to_level0_rejects_negative_downsample(self) -> None:
        """Test that size_to_level0 raises ValueError for negative downsample."""
        with pytest.raises(ValueError, match=r"must be positive.*got -10"):
            size_to_level0((100, 100), downsample=-10.0)
