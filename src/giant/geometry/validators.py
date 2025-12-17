"""Geometry validation utilities for GIANT.

This module provides bounds checking and region clamping for ensuring
that crop regions requested by the LLM are valid within WSI boundaries.
"""

from __future__ import annotations

from giant.geometry.primitives import Region, Size


class ValidationError(Exception):
    """Raised when a region fails bounds validation.

    Attributes:
        region: The invalid region that was validated.
        bounds: The bounds it was validated against.
        message: Description of the validation failure.
    """

    def __init__(
        self,
        message: str,
        *,
        region: Region,
        bounds: Size,
    ) -> None:
        self.region = region
        self.bounds = bounds
        region_str = region.to_tuple()
        bounds_str = bounds.to_tuple()
        super().__init__(f"{message} (region={region_str}, bounds={bounds_str})")


class GeometryValidator:
    """Validator for geometry operations against WSI bounds.

    This class provides methods to check if regions are valid within
    image boundaries and to clamp invalid regions to valid bounds.

    The validator is stateless and operates purely on the inputs provided
    to each method, following the Strategy pattern.
    """

    def validate(
        self,
        region: Region,
        bounds: Size,
        *,
        strict: bool = True,
    ) -> bool:
        """Validate that a region is within bounds.

        Checks that:
        1. region.right <= bounds.width
        2. region.bottom <= bounds.height

        Note: Region x, y are already constrained to >= 0 by Pydantic.

        Args:
            region: The region to validate.
            bounds: The maximum allowed dimensions (Level-0 slide size).
            strict: If True, raise ValidationError on failure.
                If False, return False instead.

        Returns:
            True if the region is valid within bounds.

        Raises:
            ValidationError: If strict=True and region exceeds bounds.
        """
        is_valid = region.right <= bounds.width and region.bottom <= bounds.height

        if not is_valid and strict:
            violations: list[str] = []
            if region.right > bounds.width:
                violations.append(
                    f"right edge ({region.right}) exceeds width ({bounds.width})"
                )
            if region.bottom > bounds.height:
                violations.append(
                    f"bottom edge ({region.bottom}) exceeds height ({bounds.height})"
                )
            raise ValidationError(
                f"Region out of bounds: {'; '.join(violations)}",
                region=region,
                bounds=bounds,
            )

        return is_valid

    def clamp_region(self, region: Region, bounds: Size) -> Region:
        """Clamp a region to valid bounds.

        This is the recovery path for LLM errors where the model requests
        a region that extends beyond the slide boundaries. The clamping
        strategy ensures:

        1. x, y are within [0, bounds - 1]
        2. width, height respect the clamped origin
        3. Minimum dimension of 1px is preserved

        This method should only be used when explicitly chosen by the
        agent's error-recovery policy (Spec-09). Prefer strict validation
        and re-prompting the LLM in most cases.

        Args:
            region: The region to clamp.
            bounds: The maximum allowed dimensions.

        Returns:
            A new Region clamped to valid bounds.

        Example:
            >>> validator = GeometryValidator()
            >>> bounds = Size(width=1000, height=1000)
            >>> bad_region = Region(x=900, y=900, width=200, height=200)
            >>> clamped = validator.clamp_region(bad_region, bounds)
            >>> clamped.right  # Now <= 1000
            1000
        """
        # Clamp origin to valid range [0, bounds-1]
        # The -1 ensures at least 1px can fit
        clamped_x = max(0, min(region.x, bounds.width - 1))
        clamped_y = max(0, min(region.y, bounds.height - 1))

        # Calculate maximum remaining space
        max_remaining_width = bounds.width - clamped_x
        max_remaining_height = bounds.height - clamped_y

        # Clamp dimensions to remaining space, minimum 1px
        clamped_width = max(1, min(region.width, max_remaining_width))
        clamped_height = max(1, min(region.height, max_remaining_height))

        return Region(
            x=clamped_x,
            y=clamped_y,
            width=clamped_width,
            height=clamped_height,
        )

    def is_within_bounds(self, region: Region, bounds: Size) -> bool:
        """Check if region is within bounds without raising.

        Convenience method that wraps validate() with strict=False.

        Args:
            region: The region to check.
            bounds: The maximum allowed dimensions.

        Returns:
            True if region is fully within bounds.
        """
        return self.validate(region, bounds, strict=False)
