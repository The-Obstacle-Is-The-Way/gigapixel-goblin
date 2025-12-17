"""Integration tests for WSIReader with real WSI files.

These tests exercise the real OpenSlide stack against actual WSI files.
They are skipped if no test file is available.

Spec-05.5 P0 Tests:
- P0-1: Open real SVS file
- P0-2: Thumbnail generation
- P0-3: Read region at Level-0
- P0-4: Read region at max level
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from giant.wsi import WSIReader
from giant.wsi.exceptions import WSIReadError
from giant.wsi.types import WSIMetadata

pytestmark = pytest.mark.integration


class TestWSIReaderRealFile:
    """Integration tests for WSIReader with real WSI files."""

    def test_open_real_svs_file(self, wsi_test_file: Path) -> None:
        """P0-1: Open real SVS file and verify metadata."""
        with WSIReader(wsi_test_file) as reader:
            metadata = reader.get_metadata()

            # Basic metadata sanity checks
            assert isinstance(metadata, WSIMetadata)
            assert metadata.width > 0
            assert metadata.height > 0
            assert metadata.level_count >= 1
            assert len(metadata.level_dimensions) == metadata.level_count
            assert len(metadata.level_downsamples) == metadata.level_count

            # Level-0 should be the largest
            assert metadata.level_dimensions[0] == (metadata.width, metadata.height)
            assert metadata.level_downsamples[0] == 1.0

            # Downsamples should be monotonically increasing
            for i in range(1, metadata.level_count):
                assert metadata.level_downsamples[i] > metadata.level_downsamples[i - 1]

    def test_thumbnail_generation(self, wsi_test_file: Path) -> None:
        """P0-2: Thumbnail generation works correctly."""
        with WSIReader(wsi_test_file) as reader:
            thumb = reader.get_thumbnail((500, 500))

            assert isinstance(thumb, Image.Image)
            assert thumb.mode == "RGB"
            # Thumbnail should fit within requested size
            assert thumb.width <= 500
            assert thumb.height <= 500
            # Should have reasonable dimensions (not degenerate)
            assert thumb.width > 0
            assert thumb.height > 0

    def test_read_region_level_0(self, wsi_test_file: Path) -> None:
        """P0-3: Read region at Level-0."""
        with WSIReader(wsi_test_file) as reader:
            # Read a small region at Level-0
            region_size = (256, 256)
            region = reader.read_region(
                location=(0, 0),
                level=0,
                size=region_size,
            )

            assert isinstance(region, Image.Image)
            assert region.mode == "RGB"
            assert region.size == region_size

    def test_read_region_max_level(self, wsi_test_file: Path) -> None:
        """P0-4: Read region at maximum (coarsest) level."""
        with WSIReader(wsi_test_file) as reader:
            metadata = reader.get_metadata()
            max_level = metadata.level_count - 1

            # Read a region at the coarsest level
            region_size = (256, 256)
            region = reader.read_region(
                location=(0, 0),
                level=max_level,
                size=region_size,
            )

            assert isinstance(region, Image.Image)
            assert region.mode == "RGB"
            assert region.size == region_size

    def test_read_region_rgb_conversion(self, wsi_test_file: Path) -> None:
        """Verify RGBA to RGB conversion works correctly."""
        with WSIReader(wsi_test_file) as reader:
            region = reader.read_region(
                location=(0, 0),
                level=0,
                size=(100, 100),
            )

            # Should always be RGB (OpenSlide returns RGBA, we convert)
            assert region.mode == "RGB"
            # Should not have alpha channel
            assert len(region.getbands()) == 3

    def test_context_manager_cleanup(self, wsi_test_file: Path) -> None:
        """Verify context manager properly closes the slide."""
        with WSIReader(wsi_test_file) as reader:
            # Verify reader works inside context
            metadata = reader.get_metadata()
            assert metadata is not None
            assert metadata.width > 0

        # After exiting context, slide should be closed
        # Attempting to read should fail with WSIReadError
        with pytest.raises(WSIReadError):
            reader.read_region((0, 0), level=0, size=(10, 10))

    def test_multiple_regions_same_slide(self, wsi_test_file: Path) -> None:
        """Verify multiple regions can be read from the same slide."""
        with WSIReader(wsi_test_file) as reader:
            metadata = reader.get_metadata()

            # Read multiple regions
            regions = []
            for i in range(3):
                offset = i * 100
                if offset + 100 <= metadata.width and offset + 100 <= metadata.height:
                    region = reader.read_region(
                        location=(offset, offset),
                        level=0,
                        size=(100, 100),
                    )
                    regions.append(region)

            assert len(regions) >= 1
            for region in regions:
                assert region.mode == "RGB"
                assert region.size == (100, 100)
