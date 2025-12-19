"""Random patch sampling for patch baseline (Spec-11).

Paper Reference: "We sample 30 random 224x224 patches from tissue regions."
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from giant.geometry.primitives import Region
from giant.vision.constants import N_PATCHES, PATCH_SIZE

if TYPE_CHECKING:
    from giant.wsi.types import WSIMetadata


def sample_patches(
    mask: npt.NDArray[Any],
    wsi_metadata: WSIMetadata,
    n_patches: int = N_PATCHES,
    patch_size: int = PATCH_SIZE,
    seed: int = 42,
) -> list[Region]:
    """Sample N random patches from tissue regions.

    Algorithm (from Spec-11):
    1. Find all tissue pixels in the mask.
    2. Randomly select tissue pixels as patch centers.
    3. Convert center coordinates from mask space to Level-0.
    4. Compute patch bounds, clamping to slide dimensions.

    Args:
        mask: Binary tissue mask at thumbnail scale (height, width).
        wsi_metadata: WSI metadata for coordinate scaling.
        n_patches: Number of patches to sample (default: 30).
        patch_size: Size of patches in Level-0 pixels (default: 224).
        seed: Random seed for reproducibility.

    Returns:
        List of Region objects in Level-0 coordinates.

    Raises:
        ValueError: If no tissue detected in mask.
        ValueError: If unable to sample the requested number of patches.
    """
    if n_patches <= 0:
        raise ValueError(f"n_patches must be > 0, got {n_patches}")
    if patch_size <= 0:
        raise ValueError(f"patch_size must be > 0, got {patch_size}")
    if patch_size > wsi_metadata.width or patch_size > wsi_metadata.height:
        raise ValueError(
            f"patch_size {patch_size} exceeds slide dimensions "
            f"{wsi_metadata.width}x{wsi_metadata.height}"
        )
    expected_ndim = 2
    if mask.ndim != expected_ndim:
        raise ValueError(f"mask must be 2D (H,W), got shape {mask.shape}")

    rng = np.random.default_rng(seed)

    # Find all tissue pixel coordinates (y, x format in numpy)
    tissue_coords = np.argwhere(mask > 0)
    if len(tissue_coords) == 0:
        raise ValueError("No tissue detected in slide")

    mask_height, mask_width = mask.shape

    # Scale factors: thumbnail → Level-0
    scale_x = wsi_metadata.width / mask_width
    scale_y = wsi_metadata.height / mask_height

    patches: list[Region] = []
    attempts = 0
    max_attempts = n_patches * 100

    while len(patches) < n_patches and attempts < max_attempts:
        # Random tissue pixel
        idx = rng.integers(len(tissue_coords))
        ty, tx = tissue_coords[idx]  # numpy is (y, x)

        # Convert to Level-0 coordinates (center of patch)
        cx = int(tx * scale_x)
        cy = int(ty * scale_y)

        # Compute patch top-left corner
        x = cx - patch_size // 2
        y = cy - patch_size // 2

        # Clamp to slide bounds
        x = max(0, min(x, wsi_metadata.width - patch_size))
        y = max(0, min(y, wsi_metadata.height - patch_size))

        center_x = x + patch_size // 2
        center_y = y + patch_size // 2

        # Ensure the final clamped patch still satisfies the contract:
        # its center overlaps tissue in the mask coordinate space.
        mask_x = int(center_x * mask_width / wsi_metadata.width)
        mask_y = int(center_y * mask_height / wsi_metadata.height)
        mask_x = max(0, min(mask_x, mask_width - 1))
        mask_y = max(0, min(mask_y, mask_height - 1))
        if mask[mask_y, mask_x] <= 0:
            attempts += 1
            continue

        patches.append(Region(x=x, y=y, width=patch_size, height=patch_size))
        attempts += 1

    if len(patches) < n_patches:
        raise ValueError(
            f"Unable to sample {n_patches} patches from tissue mask "
            f"after {attempts} attempts"
        )

    return patches


class RandomPatchSampler:
    """Random patch sampler with configurable parameters.

    Provides an object-oriented interface for patch sampling with
    reusable configuration.

    Attributes:
        n_patches: Number of patches to sample.
        patch_size: Size of patches in Level-0 pixels.
        seed: Random seed for reproducibility.
    """

    __slots__ = ("_n_patches", "_patch_size", "_seed")

    def __init__(
        self,
        n_patches: int = N_PATCHES,
        patch_size: int = PATCH_SIZE,
        seed: int = 42,
    ) -> None:
        """Initialize sampler with parameters.

        Args:
            n_patches: Number of patches to sample (default: 30).
            patch_size: Size of patches in Level-0 pixels (default: 224).
            seed: Random seed for reproducibility.
        """
        self._n_patches = n_patches
        self._patch_size = patch_size
        self._seed = seed

    @property
    def n_patches(self) -> int:
        """Return number of patches to sample."""
        return self._n_patches

    @property
    def patch_size(self) -> int:
        """Return patch size in pixels."""
        return self._patch_size

    @property
    def seed(self) -> int:
        """Return random seed."""
        return self._seed

    def sample(
        self,
        mask: npt.NDArray[Any],
        wsi_metadata: WSIMetadata,
    ) -> list[Region]:
        """Sample patches from tissue regions.

        Args:
            mask: Binary tissue mask at thumbnail scale.
            wsi_metadata: WSI metadata for coordinate scaling.

        Returns:
            List of Region objects in Level-0 coordinates.
        """
        return sample_patches(
            mask=mask,
            wsi_metadata=wsi_metadata,
            n_patches=self._n_patches,
            patch_size=self._patch_size,
            seed=self._seed,
        )
