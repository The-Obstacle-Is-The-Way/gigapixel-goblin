"""Unit tests for WSIReader using mocked OpenSlide.

These tests mock openslide.OpenSlide to avoid needing large WSI files
in the test suite. Integration tests with real files are in tests/integration/.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import openslide
import pytest
from PIL import Image

from giant.wsi import WSIReader
from giant.wsi.exceptions import WSIOpenError, WSIReadError
from giant.wsi.reader import SUPPORTED_EXTENSIONS


class TestWSIReaderInit:
    """Tests for WSIReader initialization."""

    def test_open_nonexistent_file_raises_wsi_open_error(self, tmp_path: Path) -> None:
        """Test opening a non-existent file raises WSIOpenError."""
        fake_path = tmp_path / "nonexistent.svs"

        with pytest.raises(WSIOpenError, match="File not found"):
            WSIReader(fake_path)

    def test_open_unsupported_extension_raises_wsi_open_error(
        self, tmp_path: Path
    ) -> None:
        """Test opening unsupported file extension raises WSIOpenError."""
        fake_file = tmp_path / "file.jpg"
        fake_file.write_bytes(b"fake data")

        with pytest.raises(WSIOpenError, match="Unsupported file extension"):
            WSIReader(fake_file)

    @pytest.mark.parametrize("ext", sorted(SUPPORTED_EXTENSIONS))
    def test_supported_extensions_are_accepted(self, tmp_path: Path, ext: str) -> None:
        """Test that all supported extensions pass validation."""
        fake_file = tmp_path / f"slide{ext}"
        fake_file.write_bytes(b"fake data")

        # Should not raise during extension check, but will fail at OpenSlide
        with (
            patch("giant.wsi.reader.openslide.OpenSlide") as mock_openslide,
            pytest.raises(WSIOpenError),
        ):
            mock_openslide.side_effect = openslide.OpenSlideError("Test error")
            WSIReader(fake_file)

    def test_openslide_error_wrapped_as_wsi_open_error(self, tmp_path: Path) -> None:
        """Test OpenSlideError during init is wrapped as WSIOpenError."""
        fake_file = tmp_path / "corrupt.svs"
        fake_file.write_bytes(b"not a real svs file")

        with (
            patch("giant.wsi.reader.openslide.OpenSlide") as mock_openslide,
            pytest.raises(WSIOpenError, match="Failed to open WSI"),
        ):
            mock_openslide.side_effect = openslide.OpenSlideError("Bad file")
            WSIReader(fake_file)

    def test_path_is_resolved_to_absolute(self, tmp_path: Path) -> None:
        """Test that path is resolved to absolute path."""
        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide"):
            reader = WSIReader(fake_file)
            assert reader.path.is_absolute()
            assert reader.path == fake_file.resolve()
            reader.close()


class TestWSIReaderMetadata:
    """Tests for WSIReader.get_metadata()."""

    @pytest.fixture
    def mock_slide(self) -> MagicMock:
        """Create a mock OpenSlide object with realistic properties."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (100000, 50000)
        mock.level_count = 4
        mock.level_dimensions = (
            (100000, 50000),
            (25000, 12500),
            (6250, 3125),
            (1562, 781),
        )
        mock.level_downsamples = (1.0, 4.0, 16.0, 64.0)
        mock.properties = {
            "openslide.vendor": "aperio",
            "openslide.mpp-x": "0.25",
            "openslide.mpp-y": "0.25",
        }
        return mock

    def test_get_metadata_returns_correct_values(
        self, tmp_path: Path, mock_slide: MagicMock
    ) -> None:
        """Test metadata extraction from mock OpenSlide."""
        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock_slide):
            reader = WSIReader(fake_file)
            metadata = reader.get_metadata()

            assert metadata.width == 100000
            assert metadata.height == 50000
            assert metadata.level_count == 4
            assert metadata.level_dimensions == (
                (100000, 50000),
                (25000, 12500),
                (6250, 3125),
                (1562, 781),
            )
            assert metadata.level_downsamples == (1.0, 4.0, 16.0, 64.0)
            assert metadata.vendor == "aperio"
            assert metadata.mpp_x == 0.25
            assert metadata.mpp_y == 0.25
            reader.close()

    def test_metadata_is_cached(self, tmp_path: Path, mock_slide: MagicMock) -> None:
        """Test that metadata is cached after first call."""
        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock_slide):
            reader = WSIReader(fake_file)
            metadata1 = reader.get_metadata()
            metadata2 = reader.get_metadata()

            # Should return the same cached object
            assert metadata1 is metadata2
            reader.close()

    def test_metadata_with_missing_mpp(self, tmp_path: Path) -> None:
        """Test metadata when MPP is not available."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (50000, 50000)
        mock.level_count = 2
        mock.level_dimensions = ((50000, 50000), (12500, 12500))
        mock.level_downsamples = (1.0, 4.0)
        mock.properties = {
            "openslide.vendor": "generic-tiff",
            # No mpp-x or mpp-y
        }

        fake_file = tmp_path / "slide.tiff"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            reader = WSIReader(fake_file)
            metadata = reader.get_metadata()

            assert metadata.mpp_x is None
            assert metadata.mpp_y is None
            reader.close()

    def test_metadata_with_invalid_mpp_format(self, tmp_path: Path) -> None:
        """Test metadata handles non-numeric MPP values gracefully."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (50000, 50000)
        mock.level_count = 1
        mock.level_dimensions = ((50000, 50000),)
        mock.level_downsamples = (1.0,)
        mock.properties = {
            "openslide.vendor": "unknown",
            "openslide.mpp-x": "not-a-number",
            "openslide.mpp-y": "",
        }

        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            reader = WSIReader(fake_file)
            metadata = reader.get_metadata()

            assert metadata.mpp_x is None
            assert metadata.mpp_y is None
            reader.close()


class TestWSIReaderReadRegion:
    """Tests for WSIReader.read_region()."""

    @pytest.fixture
    def reader_with_mock(self, tmp_path: Path) -> tuple[WSIReader, MagicMock]:
        """Create a WSIReader with mocked OpenSlide."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (100000, 50000)
        mock.level_count = 4
        mock.level_dimensions = (
            (100000, 50000),
            (25000, 12500),
            (6250, 3125),
            (1562, 781),
        )
        mock.level_downsamples = (1.0, 4.0, 16.0, 64.0)
        mock.properties = {"openslide.vendor": "aperio"}

        # Create fake RGBA image for read_region return
        fake_rgba = Image.new("RGBA", (512, 512), color=(255, 0, 0, 255))
        mock.read_region.return_value = fake_rgba

        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            reader = WSIReader(fake_file)
            yield reader, mock
            reader.close()

    def test_read_region_basic(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test basic read_region call."""
        reader, mock = reader_with_mock

        result = reader.read_region((1000, 2000), level=0, size=(512, 512))

        mock.read_region.assert_called_once_with((1000, 2000), 0, (512, 512))
        assert isinstance(result, Image.Image)
        assert result.mode == "RGB"  # RGBA converted to RGB

    def test_read_region_at_different_levels(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test reading at different pyramid levels."""
        reader, mock = reader_with_mock

        for level in range(4):
            reader.read_region((0, 0), level=level, size=(256, 256))

        assert mock.read_region.call_count == 4

    def test_read_region_invalid_level_raises_error(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test invalid level raises WSIReadError."""
        reader, _ = reader_with_mock

        with pytest.raises(WSIReadError, match="Invalid level 5"):
            reader.read_region((0, 0), level=5, size=(512, 512))

    def test_read_region_negative_level_raises_error(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test negative level raises WSIReadError."""
        reader, _ = reader_with_mock

        with pytest.raises(WSIReadError, match="Invalid level -1"):
            reader.read_region((0, 0), level=-1, size=(512, 512))

    def test_read_region_invalid_size_raises_error(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test zero/negative size raises WSIReadError."""
        reader, _ = reader_with_mock

        with pytest.raises(WSIReadError, match="Invalid size"):
            reader.read_region((0, 0), level=0, size=(0, 512))

        with pytest.raises(WSIReadError, match="Invalid size"):
            reader.read_region((0, 0), level=0, size=(512, -1))

    def test_read_region_negative_location_raises_error(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test negative location raises WSIReadError."""
        reader, _ = reader_with_mock

        with pytest.raises(WSIReadError, match="Invalid location"):
            reader.read_region((-100, 0), level=0, size=(512, 512))

    def test_read_region_openslide_error_wrapped(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test OpenSlideError during read is wrapped as WSIReadError."""
        reader, mock = reader_with_mock
        mock.read_region.side_effect = openslide.OpenSlideError("Read failed")

        with pytest.raises(WSIReadError, match="Failed to read region"):
            reader.read_region((0, 0), level=0, size=(512, 512))


class TestWSIReaderThumbnail:
    """Tests for WSIReader.get_thumbnail()."""

    @pytest.fixture
    def reader_with_mock(self, tmp_path: Path) -> tuple[WSIReader, MagicMock]:
        """Create a WSIReader with mocked OpenSlide."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (100000, 50000)
        mock.level_count = 1
        mock.level_dimensions = ((100000, 50000),)
        mock.level_downsamples = (1.0,)
        mock.properties = {"openslide.vendor": "test"}

        fake_thumb = Image.new("RGBA", (1024, 512), color=(128, 128, 128, 255))
        mock.get_thumbnail.return_value = fake_thumb

        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            reader = WSIReader(fake_file)
            yield reader, mock
            reader.close()

    def test_get_thumbnail_basic(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test basic thumbnail generation."""
        reader, mock = reader_with_mock

        result = reader.get_thumbnail((1024, 1024))

        mock.get_thumbnail.assert_called_once_with((1024, 1024))
        assert isinstance(result, Image.Image)
        assert result.mode == "RGB"

    def test_get_thumbnail_invalid_size_raises_error(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test invalid thumbnail size raises WSIReadError."""
        reader, _ = reader_with_mock

        with pytest.raises(WSIReadError, match="Invalid max_size"):
            reader.get_thumbnail((0, 1024))

        with pytest.raises(WSIReadError, match="Invalid max_size"):
            reader.get_thumbnail((1024, -1))

    def test_get_thumbnail_openslide_error_wrapped(
        self, reader_with_mock: tuple[WSIReader, MagicMock]
    ) -> None:
        """Test OpenSlideError during thumbnail is wrapped as WSIReadError."""
        reader, mock = reader_with_mock
        mock.get_thumbnail.side_effect = openslide.OpenSlideError("Thumb failed")

        with pytest.raises(WSIReadError, match="Failed to generate thumbnail"):
            reader.get_thumbnail((1024, 1024))


class TestWSIReaderContextManager:
    """Tests for WSIReader context manager behavior."""

    def test_context_manager_closes_on_exit(self, tmp_path: Path) -> None:
        """Test that slide is closed when exiting context."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (1000, 1000)
        mock.level_count = 1
        mock.level_dimensions = ((1000, 1000),)
        mock.level_downsamples = (1.0,)
        mock.properties = {}

        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            with WSIReader(fake_file) as reader:
                _ = reader.get_metadata()

            mock.close.assert_called_once()

    def test_context_manager_closes_on_exception(self, tmp_path: Path) -> None:
        """Test that slide is closed even when exception occurs."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (1000, 1000)
        mock.level_count = 1
        mock.level_dimensions = ((1000, 1000),)
        mock.level_downsamples = (1.0,)
        mock.properties = {}

        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            with pytest.raises(ValueError):
                with WSIReader(fake_file):
                    raise ValueError("Test exception")

            mock.close.assert_called_once()


class TestWSIReaderBestLevel:
    """Tests for WSIReader.get_best_level_for_downsample()."""

    def test_get_best_level_for_downsample(self, tmp_path: Path) -> None:
        """Test best level selection delegates to OpenSlide."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (100000, 50000)
        mock.level_count = 4
        mock.level_dimensions = (
            (100000, 50000),
            (25000, 12500),
            (6250, 3125),
            (1562, 781),
        )
        mock.level_downsamples = (1.0, 4.0, 16.0, 64.0)
        mock.properties = {}
        mock.get_best_level_for_downsample.return_value = 2

        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            reader = WSIReader(fake_file)
            result = reader.get_best_level_for_downsample(10.0)

            assert result == 2
            mock.get_best_level_for_downsample.assert_called_once_with(10.0)
            reader.close()


class TestWSIReaderRepr:
    """Tests for WSIReader string representation."""

    def test_repr(self, tmp_path: Path) -> None:
        """Test __repr__ returns expected format."""
        mock = MagicMock(spec=openslide.OpenSlide)
        mock.dimensions = (1000, 1000)
        mock.level_count = 1
        mock.level_dimensions = ((1000, 1000),)
        mock.level_downsamples = (1.0,)
        mock.properties = {}

        fake_file = tmp_path / "slide.svs"
        fake_file.write_bytes(b"data")

        with patch("giant.wsi.reader.openslide.OpenSlide", return_value=mock):
            reader = WSIReader(fake_file)
            repr_str = repr(reader)

            assert "WSIReader" in repr_str
            assert "slide.svs" in repr_str
            reader.close()
