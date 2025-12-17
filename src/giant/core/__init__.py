"""Core algorithms for GIANT.

This package contains the core algorithmic components for GIANT navigation,
including pyramid level selection and future components like the crop pipeline.

Public API:
    - PyramidLevelSelector: Selects optimal pyramid level for region extraction.
    - SelectedLevel: NamedTuple containing level index and downsample factor.
    - LevelSelectorProtocol: Protocol for dependency injection.
"""

from giant.core.level_selector import (
    LevelSelectorProtocol,
    PyramidLevelSelector,
    SelectedLevel,
)

__all__ = [
    "LevelSelectorProtocol",
    "PyramidLevelSelector",
    "SelectedLevel",
]
