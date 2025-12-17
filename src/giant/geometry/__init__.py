"""Geometry module for GIANT.

This package provides coordinate system primitives, validation, and
visual overlay generation for navigating Whole Slide Images.

Key Components:
    - Primitives: Point, Size, Region models for Level-0 coordinates
    - Validators: Bounds checking and region clamping
    - Transforms: Level-0 <-> Level-N coordinate conversions
    - Overlays: Axis guide generation for LLM navigation

Example:
    from giant.geometry import Region, GeometryValidator, Size

    # Create a region in Level-0 coordinates
    region = Region(x=1000, y=2000, width=500, height=500)

    # Validate against slide bounds
    validator = GeometryValidator()
    bounds = Size(width=100000, height=80000)
    validator.validate(region, bounds)  # Raises if invalid

    # Or clamp to valid bounds (for error recovery)
    clamped = validator.clamp_region(region, bounds)
"""

from giant.geometry.overlay import AxisGuideGenerator, OverlayService, OverlayStyle
from giant.geometry.primitives import Point, Region, Size
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
from giant.geometry.validators import GeometryValidator, ValidationError

__all__ = [
    "AxisGuideGenerator",
    "GeometryValidator",
    "OverlayService",
    "OverlayStyle",
    "Point",
    "Region",
    "Size",
    "ValidationError",
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
