"""Integration tests for the crop pipeline with real WSI files.

These tests exercise the full crop pipeline (CropEngine + PyramidLevelSelector)
against actual WSI files.

Spec-05.5 P0 Tests:
- P0-5: Coordinate roundtrip
- P0-6: Level selection for target
- P0-7: Crop pipeline end-to-end
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from giant.core.crop_engine import CropEngine, CroppedImage
from giant.core.level_selector import PyramidLevelSelector
from giant.geometry import Region
from giant.wsi import WSIReader
from giant.wsi.types import level0_to_level, level_to_level0, size_at_level

pytestmark = pytest.mark.integration


class TestCropPipelineRealFile:
    """Integration tests for crop pipeline with real WSI files."""

    def test_crop_pipeline_end_to_end(self, wsi_test_file: Path) -> None:
        """P0-7: Full crop pipeline with real WSI file."""
        with WSIReader(wsi_test_file) as reader:
            engine = CropEngine(reader)
            metadata = reader.get_metadata()

            # Request a region
            region = Region(
                x=0,
                y=0,
                width=min(5000, metadata.width),
                height=min(4000, metadata.height),
            )
            result = engine.crop(region, target_size=1000)

            # Verify result
            assert isinstance(result, CroppedImage)
            assert result.original_region == region
            assert result.read_level >= 0
            assert result.read_level < metadata.level_count
            assert result.scale_factor > 0
            assert result.scale_factor <= 1.0  # Never upsample

            # Verify image
            assert result.image.mode == "RGB"
            long_side = max(result.image.width, result.image.height)
            # Should be target_size or smaller (never upsample)
            assert long_side <= 1000

            # Verify base64 is valid JPEG
            decoded = base64.b64decode(result.base64_content)
            img = Image.open(BytesIO(decoded))
            assert img.format == "JPEG"

    def test_level_selection_for_target(self, wsi_test_file: Path) -> None:
        """P0-6: Level selection chooses appropriate pyramid level."""
        with WSIReader(wsi_test_file) as reader:
            selector = PyramidLevelSelector()
            metadata = reader.get_metadata()

            # Request a moderate-sized region
            region = Region(
                x=0,
                y=0,
                width=min(10000, metadata.width),
                height=min(8000, metadata.height),
            )

            selected = selector.select_level(
                region, metadata, target_size=1000, bias=0.85
            )

            # Should select a valid level
            assert selected.level >= 0
            assert selected.level < metadata.level_count
            assert selected.downsample > 0

            # The selected level should make sense for the target size
            # (we don't want to over-read if a coarser level would suffice)
            region_long_side_at_level = max(
                size_at_level((region.width, region.height), selected.downsample)
            )
            # For regions larger than the target at L0, the selector should avoid
            # undershooting.
            if max(region.width, region.height) >= 1000:
                assert region_long_side_at_level >= 1000

    def test_coordinate_roundtrip(self, wsi_test_file: Path) -> None:
        """P0-5: Coordinate roundtrip stays within ±downsample."""
        with WSIReader(wsi_test_file) as reader:
            metadata = reader.get_metadata()

            x = min(12345, max(0, metadata.width - 1))
            y = min(67890, max(0, metadata.height - 1))
            coord_level0 = (x, y)

            for downsample in metadata.level_downsamples:
                coord_level = level0_to_level(coord_level0, downsample)
                roundtrip = level_to_level0(coord_level, downsample)
                assert abs(roundtrip[0] - coord_level0[0]) <= downsample
                assert abs(roundtrip[1] - coord_level0[1]) <= downsample

    def test_aspect_ratio_preserved(self, wsi_test_file: Path) -> None:
        """Aspect ratio is preserved after resize."""
        with WSIReader(wsi_test_file) as reader:
            engine = CropEngine(reader)
            metadata = reader.get_metadata()

            # Request a region with specific aspect ratio
            width = min(4000, metadata.width)
            height = min(2000, metadata.height)
            region = Region(x=0, y=0, width=width, height=height)

            result = engine.crop(region, target_size=1000)

            # Calculate expected and actual aspect ratios
            original_ratio = width / height
            result_ratio = result.image.width / result.image.height

            # Allow small tolerance for rounding
            assert abs(original_ratio - result_ratio) < 0.01

    def test_different_target_sizes(self, wsi_test_file: Path) -> None:
        """Pipeline works with different target sizes."""
        with WSIReader(wsi_test_file) as reader:
            engine = CropEngine(reader)
            metadata = reader.get_metadata()

            region = Region(
                x=0,
                y=0,
                width=min(5000, metadata.width),
                height=min(4000, metadata.height),
            )

            for target_size in [500, 1000, 2000]:
                result = engine.crop(region, target_size=target_size)
                long_side = max(result.image.width, result.image.height)
                # Should be at most target_size (never upsample)
                assert long_side <= target_size

    def test_small_region_no_upsample(self, wsi_test_file: Path) -> None:
        """Small regions are returned at native resolution (no upsample)."""
        with WSIReader(wsi_test_file) as reader:
            engine = CropEngine(reader)

            # Request a region smaller than target_size
            region = Region(x=0, y=0, width=500, height=400)

            result = engine.crop(region, target_size=1000)

            # Should return at native size (no upsample)
            # Level selector chooses Level-0 for small regions, so image
            # size equals region size and no resize is applied
            assert result.image.width <= 1000
            assert result.image.height <= 1000
            assert result.scale_factor == 1.0  # No resize applied
