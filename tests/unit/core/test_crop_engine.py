"""Unit tests for CropEngine image cropping and resampling pipeline.

Tests CropEngine including:
- End-to-end flow with mocked dependencies
- Resize math preserving aspect ratio
- Base64 encoding
- Edge cases (extreme aspect ratios, small regions)
- Dependency injection
"""

from __future__ import annotations

import base64
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from giant.core.crop_engine import CropEngine, CroppedImage
from giant.core.level_selector import PyramidLevelSelector, SelectedLevel
from giant.geometry import Region
from giant.wsi.types import WSIMetadata

_DUMMY_BASE64 = "dGVzdA=="


class _FakeImage:
    """A lightweight stand-in for PIL.Image.Image for property tests.

    Avoids allocating huge image buffers while still exercising the resize
    math in CropEngine (width/height/size and resize calls).
    """

    def __init__(self, size: tuple[int, int]) -> None:
        self._size = size
        self.width, self.height = size

    @property
    def size(self) -> tuple[int, int]:
        return self._size

    def resize(
        self,
        size: tuple[int, int],
        resample: Image.Resampling = Image.Resampling.NEAREST,
        **_: object,
    ) -> _FakeImage:
        assert resample == Image.Resampling.LANCZOS
        return _FakeImage(size)


class _NoEncodeCropEngine(CropEngine):
    """CropEngine variant that skips JPEG encoding for fast property tests."""

    def _encode_base64_jpeg(self, image: Image.Image, quality: int) -> str:
        return _DUMMY_BASE64


def _fake_read_region(
    location: tuple[int, int],
    level: int,
    size: tuple[int, int],
) -> _FakeImage:
    del location, level
    return _FakeImage(size)


# --- Fixtures ---


@pytest.fixture
def mock_wsi_reader() -> MagicMock:
    """Create a mock WSI reader with standard metadata."""
    reader = MagicMock()
    reader.get_metadata.return_value = WSIMetadata(
        path="/path/to/slide.svs",
        width=100000,
        height=80000,
        level_count=3,
        level_dimensions=(
            (100000, 80000),
            (25000, 20000),
            (6250, 5000),
        ),
        level_downsamples=(1.0, 4.0, 16.0),
        vendor="aperio",
        mpp_x=0.25,
        mpp_y=0.25,
    )

    # Return a simple RGB image when read_region is called
    def mock_read_region(
        location: tuple[int, int],
        level: int,
        size: tuple[int, int],
    ) -> Image.Image:
        # Create an image of the requested size
        return Image.new("RGB", size, color=(128, 128, 128))

    reader.read_region.side_effect = mock_read_region
    return reader


@pytest.fixture
def mock_level_selector() -> MagicMock:
    """Create a mock level selector."""
    selector = MagicMock()
    selector.select_level.return_value = SelectedLevel(level=1, downsample=4.0)
    return selector


@pytest.fixture
def crop_engine(
    mock_wsi_reader: MagicMock,
    mock_level_selector: MagicMock,
) -> CropEngine:
    """Create a CropEngine with mocked dependencies."""
    return CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)


# --- Test CroppedImage ---


class TestCroppedImage:
    """Tests for CroppedImage dataclass."""

    def test_cropped_image_creation(self) -> None:
        """Test CroppedImage can be created with all fields."""
        image = Image.new("RGB", (100, 100))
        region = Region(x=0, y=0, width=1000, height=800)

        cropped = CroppedImage(
            image=image,
            base64_content="dGVzdA==",
            original_region=region,
            read_level=1,
            scale_factor=0.5,
        )

        assert cropped.image == image
        assert cropped.base64_content == "dGVzdA=="
        assert cropped.original_region == region
        assert cropped.read_level == 1
        assert cropped.scale_factor == 0.5

    def test_cropped_image_immutability(self) -> None:
        """Test CroppedImage is immutable (frozen dataclass)."""
        image = Image.new("RGB", (100, 100))
        region = Region(x=0, y=0, width=1000, height=800)

        cropped = CroppedImage(
            image=image,
            base64_content="dGVzdA==",
            original_region=region,
            read_level=1,
            scale_factor=0.5,
        )

        with pytest.raises(AttributeError):
            cropped.read_level = 2  # type: ignore[misc]


# --- Test CropEngine Initialization ---


class TestCropEngineInit:
    """Tests for CropEngine initialization."""

    def test_init_with_reader_and_selector(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test CropEngine can be initialized with reader and selector."""
        engine = CropEngine(
            reader=mock_wsi_reader,
            level_selector=mock_level_selector,
        )
        assert engine._reader == mock_wsi_reader
        assert engine._level_selector == mock_level_selector

    def test_init_with_default_level_selector(
        self,
        mock_wsi_reader: MagicMock,
    ) -> None:
        """Test CropEngine creates default PyramidLevelSelector if none provided."""
        engine = CropEngine(reader=mock_wsi_reader)
        assert isinstance(engine._level_selector, PyramidLevelSelector)


# --- Test End-to-End Crop Flow ---


class TestCropEngineEndToEnd:
    """Tests for the complete crop workflow."""

    def test_crop_calls_level_selector(
        self,
        crop_engine: CropEngine,
        mock_level_selector: MagicMock,
        mock_wsi_reader: MagicMock,
    ) -> None:
        """Test crop() calls level selector with correct parameters."""
        region = Region(x=1000, y=2000, width=10000, height=8000)

        crop_engine.crop(region, target_size=1000, bias=0.85)

        mock_level_selector.select_level.assert_called_once_with(
            region,
            mock_wsi_reader.get_metadata.return_value,
            target_size=1000,
            bias=0.85,
        )

    def test_crop_calls_read_region_with_transformed_size(
        self,
        crop_engine: CropEngine,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test crop() calls read_region with correctly transformed size."""
        region = Region(x=1000, y=2000, width=10000, height=8000)
        # Mock returns level 1 with ds=4.0
        # Expected size at level: (10000/4, 8000/4) = (2500, 2000)

        crop_engine.crop(region, target_size=1000)

        mock_wsi_reader.read_region.assert_called_once_with(
            location=(1000, 2000),
            level=1,
            size=(2500, 2000),
        )

    def test_crop_returns_cropped_image_with_metadata(
        self,
        crop_engine: CropEngine,
    ) -> None:
        """Test crop() returns CroppedImage with correct metadata."""
        region = Region(x=0, y=0, width=10000, height=8000)

        result = crop_engine.crop(region, target_size=1000)

        assert isinstance(result, CroppedImage)
        assert result.original_region == region
        assert result.read_level == 1

    def test_crop_resizes_image_to_target_size(
        self,
        crop_engine: CropEngine,
    ) -> None:
        """Test crop() resizes image so long side equals target_size."""
        region = Region(x=0, y=0, width=10000, height=8000)

        result = crop_engine.crop(region, target_size=1000)

        # Long side should be exactly 1000
        assert max(result.image.width, result.image.height) == 1000
        # Aspect ratio preserved: 10000/8000 = 1.25, so 1000/800
        assert result.image.size == (1000, 800)

    def test_crop_generates_valid_base64(
        self,
        crop_engine: CropEngine,
    ) -> None:
        """Test crop() generates valid base64 JPEG content."""
        region = Region(x=0, y=0, width=10000, height=8000)

        result = crop_engine.crop(region, target_size=1000)

        # Verify base64 is valid and decodes to JPEG
        decoded = base64.b64decode(result.base64_content)
        img = Image.open(BytesIO(decoded))
        assert img.format == "JPEG"

    def test_crop_calculates_correct_scale_factor(
        self,
        crop_engine: CropEngine,
    ) -> None:
        """Test crop() calculates correct scale factor."""
        region = Region(x=0, y=0, width=10000, height=8000)
        # Level 1 with ds=4.0: read size = (2500, 2000)
        # Resize to target_size=1000: (1000, 800)
        # Scale factor = 1000 / 2500 = 0.4

        result = crop_engine.crop(region, target_size=1000)

        assert result.scale_factor == pytest.approx(0.4)


# --- Test Resize Math ---


class TestCropEngineResizeMath:
    """Tests for resize dimension calculations."""

    def test_resize_landscape_region(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test resize of landscape region (width > height)."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=2000, height=1000)
        result = engine.crop(region, target_size=500)

        # Width is long side: 2000 → 500
        # Height scales: 1000 → 250
        assert result.image.size == (500, 250)

    def test_resize_portrait_region(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test resize of portrait region (height > width)."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=1000, height=2000)
        result = engine.crop(region, target_size=500)

        # Height is long side: 2000 → 500
        # Width scales: 1000 → 250
        assert result.image.size == (250, 500)

    def test_resize_square_region(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test resize of square region (width == height)."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=2000, height=2000)
        result = engine.crop(region, target_size=500)

        # Both sides scale equally: 2000 → 500
        assert result.image.size == (500, 500)

    def test_resize_uses_lanczos_resampling(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test that resizing uses LANCZOS resampling."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        # Force a resize (downsample) path.
        region = Region(x=0, y=0, width=2000, height=1000)
        image = Image.new("RGB", (2000, 1000))
        mock_wsi_reader.read_region.side_effect = lambda location, level, size: image

        with patch.object(image, "resize", wraps=image.resize) as mock_resize:
            engine.crop(region, target_size=500)
            assert mock_resize.call_args.kwargs["resample"] == Image.Resampling.LANCZOS

    def test_resize_extreme_landscape_aspect_ratio(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test resize of extreme landscape (very wide)."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=10000, height=100)
        result = engine.crop(region, target_size=1000)

        # Width is long side: 10000 → 1000
        # Height scales: 100 → 10
        assert result.image.size == (1000, 10)

    def test_resize_extreme_portrait_aspect_ratio(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test resize of extreme portrait (very tall)."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=100, height=10000)
        result = engine.crop(region, target_size=1000)

        # Height is long side: 10000 → 1000
        # Width scales: 100 → 10
        assert result.image.size == (10, 1000)


# --- Test Small Region Handling ---


class TestCropEngineSmallRegions:
    """Tests for handling regions smaller than target_size."""

    def test_region_smaller_than_target_no_upsample(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test region smaller than target_size returns at original size."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=500, height=400)
        result = engine.crop(region, target_size=1000)

        # Should NOT upsample - return at read size
        assert result.image.size == (500, 400)
        assert result.scale_factor == 1.0

    def test_very_small_region(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test very small region (e.g., 10x10)."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=10, height=10)
        result = engine.crop(region, target_size=1000)

        # Should NOT upsample
        assert result.image.size == (10, 10)
        assert result.scale_factor == 1.0


# --- Test Level Selection Integration ---


class TestCropEngineLevelSelection:
    """Tests for level selection integration."""

    def test_uses_real_pyramid_level_selector(
        self,
        mock_wsi_reader: MagicMock,
    ) -> None:
        """Test CropEngine works with real PyramidLevelSelector."""
        engine = CropEngine(reader=mock_wsi_reader)

        region = Region(x=0, y=0, width=10000, height=8000)
        result = engine.crop(region, target_size=1000)

        # With standard metadata, should select level 1 (ds=4.0)
        assert result.read_level == 1

    def test_respects_bias_parameter(
        self,
        mock_wsi_reader: MagicMock,
    ) -> None:
        """Test bias parameter is passed to level selector."""
        engine = CropEngine(reader=mock_wsi_reader)

        region = Region(x=0, y=0, width=10000, height=8000)

        selector = engine._level_selector
        with patch.object(
            selector, "select_level", wraps=selector.select_level
        ) as mock_select:
            engine.crop(region, target_size=1000, bias=0.5)
            mock_select.assert_called_once()
            call_args = mock_select.call_args
            assert call_args.kwargs["bias"] == 0.5


# --- Test Base64 Encoding ---


class TestCropEngineBase64:
    """Tests for Base64 encoding functionality."""

    def test_default_jpeg_quality(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test default JPEG quality is 85."""
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=10000, height=8000)

        with patch("giant.core.crop_engine.BytesIO") as mock_bytesio:
            mock_buffer = BytesIO()
            mock_bytesio.return_value = mock_buffer

            # We need to patch Image.save to capture quality parameter
            with patch.object(Image.Image, "save") as mock_save:
                engine.crop(region, target_size=1000)
                # The save should be called with quality=85
                mock_save.assert_called_once()
                call_kwargs = mock_save.call_args.kwargs
                assert call_kwargs.get("quality") == 85

    def test_custom_jpeg_quality(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test custom JPEG quality can be specified."""
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=10000, height=8000)

        with patch.object(Image.Image, "save") as mock_save:
            engine.crop(region, target_size=1000, jpeg_quality=95)
            call_kwargs = mock_save.call_args.kwargs
            assert call_kwargs.get("quality") == 95

    def test_base64_is_standard_encoding(
        self,
        crop_engine: CropEngine,
    ) -> None:
        """Test base64 uses standard encoding (no URL-safe, no newlines)."""
        region = Region(x=0, y=0, width=10000, height=8000)

        result = crop_engine.crop(region, target_size=1000)

        # Standard base64 should not have URL-safe chars
        assert "-" not in result.base64_content
        assert "_" not in result.base64_content
        # Should not have newlines
        assert "\n" not in result.base64_content


# --- Test Input Validation ---


class TestCropEngineValidation:
    """Tests for input parameter validation."""

    def test_rejects_jpeg_quality_below_1(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test crop() rejects jpeg_quality below 1."""
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)
        region = Region(x=0, y=0, width=1000, height=1000)
        with pytest.raises(ValueError, match="jpeg_quality must be"):
            engine.crop(region, target_size=1000, jpeg_quality=0)

    def test_rejects_jpeg_quality_above_100(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test crop() rejects jpeg_quality above 100."""
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)
        region = Region(x=0, y=0, width=1000, height=1000)
        with pytest.raises(ValueError, match="jpeg_quality must be"):
            engine.crop(region, target_size=1000, jpeg_quality=101)

    def test_accepts_jpeg_quality_boundary_1(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test crop() accepts jpeg_quality=1 (minimum valid)."""
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)
        region = Region(x=0, y=0, width=10000, height=8000)
        # Should not raise
        result = engine.crop(region, target_size=1000, jpeg_quality=1)
        assert result is not None

    def test_accepts_jpeg_quality_boundary_100(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test crop() accepts jpeg_quality=100 (maximum valid)."""
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)
        region = Region(x=0, y=0, width=10000, height=8000)
        # Should not raise
        result = engine.crop(region, target_size=1000, jpeg_quality=100)
        assert result is not None


# --- Test Edge Cases ---


class TestCropEngineEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_region_at_slide_boundary(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test region at the edge of slide coordinates."""
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=0, downsample=1.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        # Region at far corner of slide
        region = Region(x=90000, y=70000, width=1000, height=800)
        result = engine.crop(region, target_size=1000)

        # Should complete without error
        assert result.read_level == 0
        mock_wsi_reader.read_region.assert_called_once_with(
            location=(90000, 70000),
            level=0,
            size=(1000, 800),
        )

    def test_different_downsample_factors(
        self,
        mock_wsi_reader: MagicMock,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test with non-power-of-2 downsample factors."""
        mock_wsi_reader.get_metadata.return_value = WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=80000,
            level_count=3,
            level_dimensions=(
                (100000, 80000),
                (33333, 26666),
                (11111, 8888),
            ),
            level_downsamples=(1.0, 3.0, 9.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )
        mock_level_selector.select_level.return_value = SelectedLevel(
            level=1, downsample=3.0
        )
        engine = CropEngine(reader=mock_wsi_reader, level_selector=mock_level_selector)

        region = Region(x=0, y=0, width=9000, height=6000)
        result = engine.crop(region, target_size=1000)

        # At level 1 (ds=3.0): size = (3000, 2000)
        mock_wsi_reader.read_region.assert_called_once_with(
            location=(0, 0),
            level=1,
            size=(3000, 2000),
        )
        # Long side 3000 → 1000, short side 2000 → 666 (rounded)
        assert max(result.image.width, result.image.height) == 1000


# --- Property-Based Tests ---


class TestCropEngineProperties:
    """Property-based tests for invariants."""

    @given(
        region_width=st.integers(min_value=100, max_value=50000),
        region_height=st.integers(min_value=100, max_value=50000),
        target_size=st.integers(min_value=100, max_value=2000),
    )
    @settings(max_examples=100, deadline=None)
    def test_long_side_never_exceeds_target_or_original(
        self,
        region_width: int,
        region_height: int,
        target_size: int,
    ) -> None:
        """Verify long side is min(target_size, original_long_side)."""
        mock_reader = MagicMock()
        mock_reader.get_metadata.return_value = WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=80000,
            level_count=1,
            level_dimensions=((100000, 80000),),
            level_downsamples=(1.0,),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )
        mock_reader.read_region.side_effect = _fake_read_region

        mock_selector = MagicMock()
        mock_selector.select_level.return_value = SelectedLevel(level=0, downsample=1.0)

        engine = _NoEncodeCropEngine(reader=mock_reader, level_selector=mock_selector)

        region = Region(x=0, y=0, width=region_width, height=region_height)
        result = engine.crop(region, target_size=target_size)

        original_long_side = max(region_width, region_height)
        result_long_side = max(result.image.width, result.image.height)

        # Never exceed target_size (unless original is smaller - no upsample)
        expected_long_side = min(target_size, original_long_side)
        assert result_long_side == expected_long_side

    @given(
        region_width=st.integers(min_value=1000, max_value=10000),
        region_height=st.integers(min_value=1000, max_value=10000),
        target_size=st.integers(min_value=200, max_value=2000),
    )
    @settings(max_examples=100, deadline=None)
    def test_aspect_ratio_preserved(
        self,
        region_width: int,
        region_height: int,
        target_size: int,
    ) -> None:
        """Verify aspect ratio is preserved within rounding tolerance.

        Uses constrained inputs (max 10:1 aspect ratio, target >= 200)
        to avoid edge cases where integer rounding causes significant error.
        Extreme aspect ratios at tiny sizes are not representative of
        real pathology imaging scenarios.
        """
        mock_reader = MagicMock()
        mock_reader.get_metadata.return_value = WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=80000,
            level_count=1,
            level_dimensions=((100000, 80000),),
            level_downsamples=(1.0,),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )
        mock_reader.read_region.side_effect = _fake_read_region

        mock_selector = MagicMock()
        mock_selector.select_level.return_value = SelectedLevel(level=0, downsample=1.0)

        engine = _NoEncodeCropEngine(reader=mock_reader, level_selector=mock_selector)

        region = Region(x=0, y=0, width=region_width, height=region_height)
        result = engine.crop(region, target_size=target_size)

        # Compare aspect ratios
        original_aspect = region_width / region_height
        result_aspect = result.image.width / result.image.height

        # Allow 3% tolerance for rounding
        # Constrained inputs prevent extreme edge cases
        assert result_aspect == pytest.approx(original_aspect, rel=0.03)


# --- Test CropEngineProtocol ---


class TestCropEngineProtocol:
    """Tests for protocol compliance and dependency injection."""

    def test_accepts_any_wsi_reader_protocol(
        self,
        mock_level_selector: MagicMock,
    ) -> None:
        """Test CropEngine accepts any object implementing WSIReaderProtocol."""

        # Create a minimal mock that implements the protocol
        class MinimalReader:
            def get_metadata(self) -> WSIMetadata:
                return WSIMetadata(
                    path="/path/to/slide.svs",
                    width=1000,
                    height=800,
                    level_count=1,
                    level_dimensions=((1000, 800),),
                    level_downsamples=(1.0,),
                    vendor="test",
                    mpp_x=None,
                    mpp_y=None,
                )

            def read_region(
                self,
                location: tuple[int, int],
                level: int,
                size: tuple[int, int],
            ) -> Image.Image:
                return Image.new("RGB", size)

            def get_thumbnail(self, max_size: tuple[int, int]) -> Image.Image:
                return Image.new("RGB", max_size)

            def close(self) -> None:
                pass

        reader = MinimalReader()
        engine = CropEngine(reader=reader, level_selector=mock_level_selector)  # type: ignore[arg-type]

        region = Region(x=0, y=0, width=500, height=400)
        result = engine.crop(region, target_size=1000)

        assert isinstance(result, CroppedImage)

    def test_accepts_any_level_selector_protocol(
        self,
        mock_wsi_reader: MagicMock,
    ) -> None:
        """Test CropEngine accepts any object implementing LevelSelectorProtocol."""

        # Create a minimal mock that implements the protocol
        class MinimalSelector:
            def select_level(
                self,
                region: Region,
                metadata: WSIMetadata,
                target_size: int = 1000,
                bias: float = 0.85,
            ) -> SelectedLevel:
                return SelectedLevel(level=0, downsample=1.0)

        selector = MinimalSelector()
        engine = CropEngine(reader=mock_wsi_reader, level_selector=selector)  # type: ignore[arg-type]

        region = Region(x=0, y=0, width=5000, height=4000)
        result = engine.crop(region, target_size=1000)

        assert isinstance(result, CroppedImage)
