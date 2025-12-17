"""Core algorithms for GIANT.

This package contains the core algorithmic components for GIANT navigation,
including pyramid level selection and the crop pipeline.

Public API:
    - PyramidLevelSelector: Selects optimal pyramid level for region extraction.
    - SelectedLevel: NamedTuple containing level index and downsample factor.
    - LevelSelectorProtocol: Protocol for dependency injection.
    - CropEngine: Orchestrates region extraction, resampling, and encoding.
    - CroppedImage: Result container with image and metadata.
"""

from giant.core.crop_engine import CropEngine, CroppedImage
from giant.core.level_selector import (
    LevelSelectorProtocol,
    PyramidLevelSelector,
    SelectedLevel,
)

__all__ = [
    "CropEngine",
    "CroppedImage",
    "LevelSelectorProtocol",
    "PyramidLevelSelector",
    "SelectedLevel",
]
