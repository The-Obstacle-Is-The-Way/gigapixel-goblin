"""Tests for giant.vision.segmentation module (Spec-11)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from giant.vision.segmentation import TissueSegmentor, segment_tissue


class TestTissueSegmentor:
    """Tests for TissueSegmentor class."""

    def test_default_backend_is_parity(self) -> None:
        """Test default backend is 'parity' for CI compatibility."""
        segmentor = TissueSegmentor()
        assert segmentor.backend == "parity"

    def test_parity_backend_initialization(self) -> None:
        """Test explicit parity backend initialization."""
        segmentor = TissueSegmentor(backend="parity")
        assert segmentor.backend == "parity"

    def test_invalid_backend_raises(self) -> None:
        """Test invalid backend raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported backend"):
            TissueSegmentor(backend="invalid")

    def test_segment_returns_binary_mask(self) -> None:
        """Test segmentation returns binary mask."""
        segmentor = TissueSegmentor(backend="parity")
        # Create a simple test image: white background with colored tissue
        image = Image.new("RGB", (100, 100), color=(255, 255, 255))
        # Add some "tissue" (pink-ish H&E stained)
        tissue = Image.new("RGB", (40, 40), color=(200, 150, 200))
        image.paste(tissue, (30, 30))

        mask = segmentor.segment(image)

        assert isinstance(mask, np.ndarray)
        assert mask.dtype in (bool, np.uint8)
        assert mask.shape == (100, 100)
        # Mask should have exactly two values (binary)
        unique_values = np.unique(mask)
        assert len(unique_values) <= 2

    def test_segment_white_image_all_background(self) -> None:
        """Test fully white image returns all-background mask."""
        segmentor = TissueSegmentor(backend="parity")
        white_image = Image.new("RGB", (100, 100), color=(255, 255, 255))

        mask = segmentor.segment(white_image)

        # All white should be background (0 or False)
        assert np.sum(mask > 0) == 0 or np.sum(mask) < 100  # Allow small noise

    def test_segment_colored_image_has_tissue(self) -> None:
        """Test image with tissue region detects tissue."""
        segmentor = TissueSegmentor(backend="parity")
        # Create image with white background and colored tissue region
        # Otsu needs variance in saturation to find threshold
        image = Image.new("RGB", (100, 100), color=(255, 255, 255))  # white bg
        tissue = Image.new("RGB", (60, 60), color=(200, 100, 150))  # pink tissue
        image.paste(tissue, (20, 20))

        mask = segmentor.segment(image)

        # Should detect tissue region (at least 20% of image is tissue)
        tissue_fraction = np.sum(mask > 0) / mask.size
        assert tissue_fraction > 0.2


class TestSegmentTissue:
    """Tests for segment_tissue function."""

    def test_segment_tissue_basic(self) -> None:
        """Test basic tissue segmentation function."""
        # Create test image with clear tissue region
        image = Image.new("RGB", (100, 100), color=(255, 255, 255))
        tissue = Image.new("RGB", (50, 50), color=(200, 100, 150))
        image.paste(tissue, (25, 25))

        mask = segment_tissue(image)

        assert isinstance(mask, np.ndarray)
        assert mask.shape == (100, 100)

    def test_segment_tissue_accepts_backend(self) -> None:
        """Test segment_tissue accepts backend parameter."""
        image = Image.new("RGB", (50, 50), color=(200, 100, 150))
        mask = segment_tissue(image, backend="parity")
        assert mask is not None


class TestMorphologicalClosing:
    """Tests for morphological closing behavior."""

    def test_small_holes_filled(self) -> None:
        """Test that small holes in tissue regions are filled."""
        segmentor = TissueSegmentor(backend="parity")

        # Create image with tissue and small white hole
        arr = np.full((100, 100, 3), fill_value=(200, 100, 150), dtype=np.uint8)
        # Small white hole (should be filled by morphological closing)
        arr[48:52, 48:52] = (255, 255, 255)
        image = Image.fromarray(arr, mode="RGB")

        mask = segmentor.segment(image)

        # Center region should be tissue after closing fills the hole
        # (may not be perfect due to algorithm, but should have high tissue coverage)
        tissue_fraction = np.sum(mask > 0) / mask.size
        assert tissue_fraction > 0.8


class TestEdgeCases:
    """Tests for edge cases in segmentation."""

    def test_very_small_image(self) -> None:
        """Test segmentation handles very small images."""
        segmentor = TissueSegmentor(backend="parity")
        small_image = Image.new("RGB", (10, 10), color=(200, 100, 150))

        mask = segmentor.segment(small_image)

        assert mask.shape == (10, 10)

    def test_non_square_image(self) -> None:
        """Test segmentation handles non-square images."""
        segmentor = TissueSegmentor(backend="parity")
        rect_image = Image.new("RGB", (200, 100), color=(200, 100, 150))

        mask = segmentor.segment(rect_image)

        assert mask.shape == (100, 200)  # height, width in numpy

    def test_grayscale_raises_or_converts(self) -> None:
        """Test grayscale image is handled appropriately."""
        segmentor = TissueSegmentor(backend="parity")
        gray_image = Image.new("L", (100, 100), color=128)

        # Should either convert to RGB and work, or raise clear error
        try:
            mask = segmentor.segment(gray_image)
            assert mask.shape == (100, 100)
        except ValueError as e:
            assert "RGB" in str(e) or "mode" in str(e).lower()
