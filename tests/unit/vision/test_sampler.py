"""Tests for giant.vision.sampler module (Spec-11)."""

from __future__ import annotations

import numpy as np
import pytest

from giant.geometry.primitives import Region
from giant.vision.constants import N_PATCHES, PATCH_SIZE
from giant.vision.sampler import RandomPatchSampler, sample_patches
from giant.wsi.types import WSIMetadata


@pytest.fixture
def simple_metadata() -> WSIMetadata:
    """Create simple WSI metadata for testing."""
    return WSIMetadata(
        path="/test/slide.svs",
        width=10000,
        height=10000,
        level_count=3,
        level_dimensions=((10000, 10000), (2500, 2500), (625, 625)),
        level_downsamples=(1.0, 4.0, 16.0),
        vendor="test",
        mpp_x=0.25,
        mpp_y=0.25,
    )


@pytest.fixture
def simple_mask() -> np.ndarray:
    """Create a simple tissue mask (center region is tissue)."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[25:75, 25:75] = 255  # Center 50x50 is tissue
    return mask


class TestSamplePatches:
    """Tests for sample_patches function."""

    def test_returns_n_patches(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test returns exactly N patches by default."""
        patches = sample_patches(simple_mask, simple_metadata)
        assert len(patches) == N_PATCHES  # Default is 30

    def test_returns_custom_n_patches(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test returns custom number of patches."""
        patches = sample_patches(simple_mask, simple_metadata, n_patches=10)
        assert len(patches) == 10

    def test_returns_region_objects(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test returns list of Region objects."""
        patches = sample_patches(simple_mask, simple_metadata, n_patches=5)
        assert all(isinstance(p, Region) for p in patches)

    def test_patches_have_correct_size(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test patches have correct size (224x224 by default)."""
        patches = sample_patches(simple_mask, simple_metadata, n_patches=5)
        for patch in patches:
            assert patch.width == PATCH_SIZE
            assert patch.height == PATCH_SIZE

    def test_patches_custom_size(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test patches with custom size."""
        patches = sample_patches(
            simple_mask, simple_metadata, n_patches=5, patch_size=512
        )
        for patch in patches:
            assert patch.width == 512
            assert patch.height == 512

    def test_patches_within_bounds(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test all patches are within slide bounds."""
        patches = sample_patches(simple_mask, simple_metadata, n_patches=20)
        for patch in patches:
            assert patch.x >= 0
            assert patch.y >= 0
            assert patch.right <= simple_metadata.width
            assert patch.bottom <= simple_metadata.height

    def test_deterministic_with_seed(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test same seed produces same patches."""
        patches1 = sample_patches(simple_mask, simple_metadata, n_patches=10, seed=42)
        patches2 = sample_patches(simple_mask, simple_metadata, n_patches=10, seed=42)
        assert patches1 == patches2

    def test_different_seeds_different_patches(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test different seeds produce different patches."""
        patches1 = sample_patches(simple_mask, simple_metadata, n_patches=10, seed=42)
        patches2 = sample_patches(simple_mask, simple_metadata, n_patches=10, seed=123)
        assert patches1 != patches2

    def test_empty_mask_raises(self, simple_metadata: WSIMetadata) -> None:
        """Test empty mask (no tissue) raises ValueError."""
        empty_mask = np.zeros((100, 100), dtype=np.uint8)
        with pytest.raises(ValueError, match="No tissue detected"):
            sample_patches(empty_mask, simple_metadata, n_patches=5)

    def test_patches_from_tissue_regions(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test patches are sampled from tissue regions."""
        # Mask: tissue in center (25-75 in 100x100 thumbnail)
        # That maps to 2500-7500 in Level-0 (10000x10000)
        patches = sample_patches(simple_mask, simple_metadata, n_patches=10, seed=42)

        for patch in patches:
            # Center of patch should be within tissue region
            cx, cy = patch.center
            # Scale center back to mask coordinates
            mask_x = int(cx * simple_mask.shape[1] / simple_metadata.width)
            mask_y = int(cy * simple_mask.shape[0] / simple_metadata.height)
            # Allow some tolerance for edge patches
            assert 20 <= mask_x <= 80 and 20 <= mask_y <= 80, (
                f"Patch center ({mask_x}, {mask_y}) outside tissue region"
            )


class TestRandomPatchSampler:
    """Tests for RandomPatchSampler class."""

    def test_default_parameters(self) -> None:
        """Test sampler with default parameters."""
        sampler = RandomPatchSampler()
        assert sampler.n_patches == N_PATCHES
        assert sampler.patch_size == PATCH_SIZE

    def test_custom_parameters(self) -> None:
        """Test sampler with custom parameters."""
        sampler = RandomPatchSampler(n_patches=50, patch_size=512, seed=123)
        assert sampler.n_patches == 50
        assert sampler.patch_size == 512
        assert sampler.seed == 123

    def test_sample_method(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test sampler.sample() method."""
        sampler = RandomPatchSampler(n_patches=5, seed=42)
        patches = sampler.sample(simple_mask, simple_metadata)
        assert len(patches) == 5
        assert all(isinstance(p, Region) for p in patches)

    def test_sampler_determinism(
        self, simple_mask: np.ndarray, simple_metadata: WSIMetadata
    ) -> None:
        """Test sampler produces deterministic results."""
        sampler = RandomPatchSampler(n_patches=10, seed=42)
        patches1 = sampler.sample(simple_mask, simple_metadata)
        patches2 = sampler.sample(simple_mask, simple_metadata)
        assert patches1 == patches2


class TestEdgeCases:
    """Tests for edge cases in sampling."""

    def test_small_tissue_region(self, simple_metadata: WSIMetadata) -> None:
        """Test sampling from very small tissue region."""
        # Only a small corner has tissue
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[0:10, 0:10] = 255

        # Should still work but might not get all patches if region too small
        patches = sample_patches(mask, simple_metadata, n_patches=5, seed=42)
        assert len(patches) >= 1  # At least some patches

    def test_raises_when_center_overlap_impossible(self) -> None:
        """Test strict center-over-tissue contract is enforced after clamping."""
        small_metadata = WSIMetadata(
            path="/test/small.svs",
            width=500,
            height=500,
            level_count=1,
            level_dimensions=((500, 500),),
            level_downsamples=(1.0,),
            vendor="test",
            mpp_x=0.25,
            mpp_y=0.25,
        )
        # Single tissue pixel in the corner: any in-bounds 224x224 patch will have
        # a center far from (0,0) after clamping, so the contract cannot be met.
        mask = np.zeros((50, 50), dtype=np.uint8)
        mask[0, 0] = 255

        with pytest.raises(ValueError, match="Unable to sample"):
            sample_patches(mask, small_metadata, n_patches=1, seed=42)

    def test_full_tissue_mask(self, simple_metadata: WSIMetadata) -> None:
        """Test fully filled tissue mask."""
        full_mask = np.full((100, 100), 255, dtype=np.uint8)
        patches = sample_patches(full_mask, simple_metadata, n_patches=10)
        assert len(patches) == 10

    def test_non_square_mask(self, simple_metadata: WSIMetadata) -> None:
        """Test non-square mask."""
        rect_mask = np.zeros((50, 200), dtype=np.uint8)
        rect_mask[10:40, 50:150] = 255

        patches = sample_patches(rect_mask, simple_metadata, n_patches=5)
        assert len(patches) == 5

    def test_large_patch_size_clamped(self) -> None:
        """Test large patch size relative to slide is handled."""
        small_metadata = WSIMetadata(
            path="/test/small.svs",
            width=500,
            height=500,
            level_count=1,
            level_dimensions=((500, 500),),
            level_downsamples=(1.0,),
            vendor="test",
            mpp_x=0.25,
            mpp_y=0.25,
        )
        mask = np.full((50, 50), 255, dtype=np.uint8)

        # Patch size 224 on 500px slide - patches should be clamped
        patches = sample_patches(mask, small_metadata, n_patches=3)
        for patch in patches:
            assert patch.right <= 500
            assert patch.bottom <= 500
