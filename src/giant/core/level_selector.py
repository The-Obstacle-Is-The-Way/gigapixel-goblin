"""Pyramid level selection algorithm for GIANT.

This module implements the core heuristic used by GIANT to select the optimal
pyramid level for a given crop. The goal is to retrieve a region that, when
scaled to the target size S (default 1000px), retains maximum detail without
unnecessary processing overhead.

Paper Reference:
    "We choose the pyramid level that will render the crop to a target long side
    (default S=1000 px) while biasing toward finer levels (oversampling bias 0.85)...
    If this level undershoots S, we move one level finer."

Algorithm Invariant:
    After level selection, we always downsample (or 1:1) to reach target_size,
    never upsample, unless the region is smaller than target_size at Level-0.
"""

from __future__ import annotations

from typing import NamedTuple, Protocol

from giant.geometry import Region
from giant.wsi.types import WSIMetadata


class SelectedLevel(NamedTuple):
    """Result of pyramid level selection.

    Attributes:
        level: Pyramid level index (0 = finest/highest resolution).
        downsample: Downsample factor at this level (1.0 for Level-0).
    """

    level: int
    downsample: float


class LevelSelectorProtocol(Protocol):
    """Protocol defining the interface for level selectors.

    This protocol allows for dependency injection and alternative
    implementations (e.g., for testing or different selection strategies).
    """

    def select_level(
        self,
        region: Region,
        metadata: WSIMetadata,
        target_size: int = 1000,
        bias: float = 0.85,
    ) -> SelectedLevel:
        """Select the optimal pyramid level for extracting a region.

        Args:
            region: Requested crop in Level-0 coordinates.
            metadata: WSI metadata containing pyramid level information.
            target_size: Target long-side in pixels (default: 1000).
            bias: Oversampling bias (default: 0.85). Lower values prefer
                coarser levels; higher values prefer finer levels.

        Returns:
            SelectedLevel containing the optimal level index and downsample factor.
        """
        ...


class PyramidLevelSelector:
    """Selects optimal pyramid level for region extraction.

    Implements the GIANT paper's level selection algorithm with configurable
    oversampling bias. The algorithm:

    1. Computes target_native = target_size / bias (biased target resolution).
    2. Finds the level closest to target_native (preferring finer on tie).
    3. Applies undershoot correction: if selected level undershoots target_size,
       moves to finer levels until target_size is met or Level-0 is reached.

    Example:
        >>> selector = PyramidLevelSelector()
        >>> region = Region(x=0, y=0, width=10000, height=8000)
        >>> result = selector.select_level(region, metadata, target_size=1000)
        >>> print(f"Use level {result.level} (ds={result.downsample})")
    """

    def select_level(
        self,
        region: Region,
        metadata: WSIMetadata,
        target_size: int = 1000,
        bias: float = 0.85,
    ) -> SelectedLevel:
        """Select the optimal pyramid level for extracting a region.

        Args:
            region: Requested crop in Level-0 coordinates.
            metadata: WSI metadata containing pyramid level information.
            target_size: Target long-side in pixels (default: 1000).
            bias: Oversampling bias (default: 0.85). By dividing target_size
                by bias, we bias toward selecting levels that will oversample
                (requiring downscale to target_size) rather than undersample
                (requiring upscale).

        Returns:
            SelectedLevel containing the optimal level index and downsample factor.

        Raises:
            ValueError: If target_size is not positive.
            ValueError: If bias is not positive.
        """
        self._validate_parameters(target_size, bias)

        # Step 1: Compute target_native (biased target resolution)
        # Paper notation: L0 = region long-side in Level-0 pixels
        region_long_side = max(region.width, region.height)
        target_native = target_size / bias

        # Step 2: Find level closest to target_native, preferring finer on tie
        best_k = self._find_closest_level(region_long_side, target_native, metadata)

        # Step 3: Apply undershoot correction
        best_k = self._apply_undershoot_correction(
            best_k, region_long_side, target_size, metadata
        )

        return SelectedLevel(
            level=best_k,
            downsample=metadata.level_downsamples[best_k],
        )

    def _validate_parameters(self, target_size: int, bias: float) -> None:
        """Validate input parameters.

        Args:
            target_size: Target size to validate.
            bias: Bias value to validate.

        Raises:
            ValueError: If parameters are invalid.
        """
        if target_size <= 0:
            raise ValueError(f"target_size must be positive, got {target_size}")
        if bias <= 0:
            raise ValueError(f"bias must be positive, got {bias}")

    def _find_closest_level(
        self,
        region_long_side: int,
        target_native: float,
        metadata: WSIMetadata,
    ) -> int:
        """Find the level closest to target_native.

        Implements tie-breaker: if two levels are equidistant from target_native,
        the finer level (smaller index) is selected.

        Args:
            region_long_side: Region long-side in Level-0 pixels (paper: L0).
            target_native: Target resolution after bias adjustment.
            metadata: WSI metadata with level information.

        Returns:
            Index of the level closest to target_native.
        """
        best_k = 0
        best_diff = float("inf")

        for k, ds in enumerate(metadata.level_downsamples):
            # Paper notation: Lk = projected size at level k
            size_at_level = region_long_side / ds
            diff = abs(size_at_level - target_native)

            # Select if strictly better, or on tie if finer (smaller k)
            if diff < best_diff or (diff == best_diff and k < best_k):
                best_diff = diff
                best_k = k

        return best_k

    def _apply_undershoot_correction(
        self,
        level: int,
        region_long_side: int,
        target_size: int,
        metadata: WSIMetadata,
    ) -> int:
        """Apply undershoot correction to ensure adequate resolution.

        If the projected size at the selected level is less than target_size,
        move to finer levels until target_size is met or Level-0 is reached.

        Args:
            level: Currently selected level.
            region_long_side: Region long-side in Level-0 pixels (paper: L0).
            target_size: Minimum acceptable resolution.
            metadata: WSI metadata with level information.

        Returns:
            Corrected level index.
        """
        while level > 0:
            # Paper notation: Lk = projected size at level k
            size_at_level = region_long_side / metadata.level_downsamples[level]
            if size_at_level >= target_size:
                break
            level -= 1

        return level
