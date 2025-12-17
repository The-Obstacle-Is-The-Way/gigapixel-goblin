"""Unit tests for geometry validators.

Tests GeometryValidator including:
- validate() with strict and non-strict modes
- clamp_region() edge case handling
- ValidationError context information
"""

from __future__ import annotations

import pytest

from giant.geometry import GeometryValidator, Region, Size, ValidationError


class TestGeometryValidatorValidate:
    """Tests for GeometryValidator.validate method."""

    @pytest.fixture
    def validator(self) -> GeometryValidator:
        """Create a validator instance."""
        return GeometryValidator()

    @pytest.fixture
    def bounds(self) -> Size:
        """Create typical WSI bounds."""
        return Size(width=100000, height=80000)

    def test_validate_region_fully_inside(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test valid region fully inside bounds."""
        region = Region(x=1000, y=2000, width=5000, height=4000)
        assert validator.validate(region, bounds) is True

    def test_validate_region_at_origin(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test valid region at origin."""
        region = Region(x=0, y=0, width=1000, height=1000)
        assert validator.validate(region, bounds) is True

    def test_validate_region_at_max_extent(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test valid region touching right and bottom edges."""
        region = Region(x=99000, y=79000, width=1000, height=1000)
        assert validator.validate(region, bounds) is True

    def test_validate_region_fills_bounds(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test valid region exactly filling bounds."""
        region = Region(x=0, y=0, width=100000, height=80000)
        assert validator.validate(region, bounds) is True

    def test_validate_region_exceeds_right_strict(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test region exceeding right edge raises in strict mode."""
        region = Region(x=99000, y=0, width=2000, height=1000)  # right=101000
        with pytest.raises(ValidationError, match=r"right edge.*exceeds width"):
            validator.validate(region, bounds, strict=True)

    def test_validate_region_exceeds_bottom_strict(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test region exceeding bottom edge raises in strict mode."""
        region = Region(x=0, y=79000, width=1000, height=2000)  # bottom=81000
        with pytest.raises(ValidationError, match=r"bottom edge.*exceeds height"):
            validator.validate(region, bounds, strict=True)

    def test_validate_region_exceeds_both_strict(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test region exceeding both edges includes both violations."""
        region = Region(x=99000, y=79000, width=2000, height=2000)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(region, bounds, strict=True)
        assert "right edge" in str(exc_info.value)
        assert "bottom edge" in str(exc_info.value)

    def test_validate_region_exceeds_right_non_strict(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test region exceeding right edge returns False in non-strict mode."""
        region = Region(x=99000, y=0, width=2000, height=1000)
        assert validator.validate(region, bounds, strict=False) is False

    def test_validate_region_exceeds_bottom_non_strict(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test region exceeding bottom edge returns False in non-strict mode."""
        region = Region(x=0, y=79000, width=1000, height=2000)
        assert validator.validate(region, bounds, strict=False) is False

    def test_validate_default_is_strict(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test validate defaults to strict mode."""
        region = Region(x=99000, y=0, width=2000, height=1000)
        with pytest.raises(ValidationError):
            validator.validate(region, bounds)


class TestGeometryValidatorClampRegion:
    """Tests for GeometryValidator.clamp_region method."""

    @pytest.fixture
    def validator(self) -> GeometryValidator:
        """Create a validator instance."""
        return GeometryValidator()

    @pytest.fixture
    def bounds(self) -> Size:
        """Create typical bounds."""
        return Size(width=1000, height=1000)

    def test_clamp_region_fully_inside(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping region that's already valid."""
        region = Region(x=100, y=100, width=200, height=200)
        clamped = validator.clamp_region(region, bounds)
        assert clamped == region

    def test_clamp_region_exceeds_right(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping region exceeding right edge."""
        region = Region(x=900, y=100, width=200, height=100)  # right=1100
        clamped = validator.clamp_region(region, bounds)
        assert clamped.x == 900
        assert clamped.y == 100
        assert clamped.width == 100  # Truncated to fit
        assert clamped.height == 100
        assert clamped.right == 1000

    def test_clamp_region_exceeds_bottom(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping region exceeding bottom edge."""
        region = Region(x=100, y=900, width=100, height=200)  # bottom=1100
        clamped = validator.clamp_region(region, bounds)
        assert clamped.x == 100
        assert clamped.y == 900
        assert clamped.width == 100
        assert clamped.height == 100  # Truncated to fit
        assert clamped.bottom == 1000

    def test_clamp_region_x_exceeds_bounds(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping when x is beyond bounds."""
        region = Region(x=1500, y=100, width=200, height=200)  # x > bounds.width
        clamped = validator.clamp_region(region, bounds)
        assert clamped.x == 999  # Clamped to width - 1
        assert clamped.width == 1  # Minimum 1px

    def test_clamp_region_y_exceeds_bounds(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping when y is beyond bounds."""
        region = Region(x=100, y=1500, width=200, height=200)  # y > bounds.height
        clamped = validator.clamp_region(region, bounds)
        assert clamped.y == 999  # Clamped to height - 1
        assert clamped.height == 1  # Minimum 1px

    def test_clamp_region_entirely_outside(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping region entirely outside bounds."""
        region = Region(x=2000, y=2000, width=500, height=500)
        clamped = validator.clamp_region(region, bounds)
        # Should clamp to corner with minimum dimension
        assert clamped.x == 999
        assert clamped.y == 999
        assert clamped.width == 1
        assert clamped.height == 1

    def test_clamp_region_preserves_minimum_dimension(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping always preserves at least 1px dimension."""
        region = Region(x=999, y=999, width=500, height=500)
        clamped = validator.clamp_region(region, bounds)
        assert clamped.width >= 1
        assert clamped.height >= 1

    def test_clamp_region_at_corner(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping region at bottom-right corner."""
        region = Region(x=999, y=999, width=100, height=100)
        clamped = validator.clamp_region(region, bounds)
        assert clamped.x == 999
        assert clamped.y == 999
        assert clamped.width == 1
        assert clamped.height == 1

    def test_clamp_region_large_region(
        self, validator: GeometryValidator, bounds: Size
    ) -> None:
        """Test clamping region larger than bounds."""
        region = Region(x=0, y=0, width=5000, height=5000)
        clamped = validator.clamp_region(region, bounds)
        assert clamped.x == 0
        assert clamped.y == 0
        assert clamped.width == 1000
        assert clamped.height == 1000


class TestGeometryValidatorIsWithinBounds:
    """Tests for GeometryValidator.is_within_bounds convenience method."""

    @pytest.fixture
    def validator(self) -> GeometryValidator:
        """Create a validator instance."""
        return GeometryValidator()

    def test_is_within_bounds_inside(self, validator: GeometryValidator) -> None:
        """Test is_within_bounds returns True for valid region."""
        region = Region(x=100, y=100, width=200, height=200)
        bounds = Size(width=1000, height=1000)
        assert validator.is_within_bounds(region, bounds) is True

    def test_is_within_bounds_outside(self, validator: GeometryValidator) -> None:
        """Test is_within_bounds returns False for invalid region."""
        region = Region(x=900, y=100, width=200, height=200)  # right=1100
        bounds = Size(width=1000, height=1000)
        assert validator.is_within_bounds(region, bounds) is False

    def test_is_within_bounds_never_raises(self, validator: GeometryValidator) -> None:
        """Test is_within_bounds never raises ValidationError."""
        region = Region(x=5000, y=5000, width=1000, height=1000)
        bounds = Size(width=100, height=100)
        # Should not raise
        result = validator.is_within_bounds(region, bounds)
        assert result is False


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error_contains_region(self) -> None:
        """Test ValidationError contains the region."""
        region = Region(x=100, y=200, width=300, height=400)
        bounds = Size(width=1000, height=1000)
        error = ValidationError("Test error", region=region, bounds=bounds)
        assert error.region == region

    def test_validation_error_contains_bounds(self) -> None:
        """Test ValidationError contains the bounds."""
        region = Region(x=100, y=200, width=300, height=400)
        bounds = Size(width=1000, height=1000)
        error = ValidationError("Test error", region=region, bounds=bounds)
        assert error.bounds == bounds

    def test_validation_error_message_includes_context(self) -> None:
        """Test ValidationError message includes region and bounds."""
        region = Region(x=100, y=200, width=300, height=400)
        bounds = Size(width=1000, height=1000)
        error = ValidationError("Test error", region=region, bounds=bounds)
        message = str(error)
        assert "region=" in message
        assert "bounds=" in message
        assert "Test error" in message
