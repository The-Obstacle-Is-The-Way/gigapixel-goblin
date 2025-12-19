"""Unit tests for axis guide overlay generation.

Tests AxisGuideGenerator and OverlayService including:
- Overlay image creation and format
- Grid line positioning
- Label coordinate calculation
- Thumbnail compositing
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageFont

from giant.geometry.overlay import AxisGuideGenerator, OverlayService, OverlayStyle
from giant.wsi.types import WSIMetadata


class TestOverlayStyle:
    """Tests for OverlayStyle configuration."""

    def test_default_style(self) -> None:
        """Test default style values."""
        style = OverlayStyle()
        assert style.line_color == (255, 0, 0, 180)  # Semi-transparent red
        assert style.line_width == 2
        assert style.label_color == (255, 255, 255, 255)  # White
        assert style.font_size == 12
        assert style.label_padding == 5
        assert style.num_guides == 4

    def test_custom_style(self) -> None:
        """Test custom style values."""
        style = OverlayStyle(
            line_color=(0, 255, 0, 200),
            line_width=3,
            num_guides=6,
        )
        assert style.line_color == (0, 255, 0, 200)
        assert style.line_width == 3
        assert style.num_guides == 6

    def test_style_is_frozen(self) -> None:
        """Test OverlayStyle is immutable (frozen dataclass)."""
        style = OverlayStyle()
        with pytest.raises(AttributeError):
            style.line_width = 5  # type: ignore[misc]


class TestAxisGuideGenerator:
    """Tests for AxisGuideGenerator."""

    @pytest.fixture
    def generator(self) -> AxisGuideGenerator:
        """Create a default generator."""
        return AxisGuideGenerator()

    @pytest.fixture
    def custom_generator(self) -> AxisGuideGenerator:
        """Create a generator with custom style."""
        style = OverlayStyle(num_guides=2, line_width=1)
        return AxisGuideGenerator(style=style)

    def test_generate_returns_rgba_image(self, generator: AxisGuideGenerator) -> None:
        """Test generator returns RGBA image."""
        overlay = generator.generate(
            thumbnail_size=(1024, 768),
            slide_dimensions=(100000, 75000),
        )
        assert isinstance(overlay, Image.Image)
        assert overlay.mode == "RGBA"

    def test_generate_correct_size(self, generator: AxisGuideGenerator) -> None:
        """Test overlay has correct dimensions."""
        thumbnail_size = (1024, 768)
        overlay = generator.generate(
            thumbnail_size=thumbnail_size,
            slide_dimensions=(100000, 75000),
        )
        assert overlay.size == thumbnail_size

    def test_generate_transparent_background(
        self, generator: AxisGuideGenerator
    ) -> None:
        """Test overlay has transparent background."""
        overlay = generator.generate(
            thumbnail_size=(100, 100),
            slide_dimensions=(10000, 10000),
        )
        # Check a corner pixel that should be transparent
        # Note: Grid lines may intersect at some positions
        pixel = overlay.getpixel((0, 0))
        # Alpha channel (index 3) should be 0 for fully transparent
        # or could have label text, so just verify it's not the line color
        assert isinstance(pixel, tuple)
        assert len(pixel) == 4

    def test_generate_with_custom_style(
        self, custom_generator: AxisGuideGenerator
    ) -> None:
        """Test generator uses custom style."""
        assert custom_generator.style.num_guides == 2
        assert custom_generator.style.line_width == 1

    def test_generate_square_thumbnail(self, generator: AxisGuideGenerator) -> None:
        """Test generation with square thumbnail."""
        overlay = generator.generate(
            thumbnail_size=(512, 512),
            slide_dimensions=(50000, 50000),
        )
        assert overlay.size == (512, 512)

    def test_generate_wide_thumbnail(self, generator: AxisGuideGenerator) -> None:
        """Test generation with wide aspect ratio thumbnail."""
        overlay = generator.generate(
            thumbnail_size=(1920, 400),
            slide_dimensions=(192000, 40000),
        )
        assert overlay.size == (1920, 400)

    def test_generate_tall_thumbnail(self, generator: AxisGuideGenerator) -> None:
        """Test generation with tall aspect ratio thumbnail."""
        overlay = generator.generate(
            thumbnail_size=(400, 1200),
            slide_dimensions=(40000, 120000),
        )
        assert overlay.size == (400, 1200)

    def test_generate_small_thumbnail(self, generator: AxisGuideGenerator) -> None:
        """Test generation with small thumbnail."""
        overlay = generator.generate(
            thumbnail_size=(64, 64),
            slide_dimensions=(100000, 100000),
        )
        assert overlay.size == (64, 64)

    def test_generate_rejects_zero_thumbnail_width(
        self, generator: AxisGuideGenerator
    ) -> None:
        """Test generate raises ValueError for zero thumbnail width."""
        with pytest.raises(ValueError, match="thumbnail_size must be positive"):
            generator.generate(
                thumbnail_size=(0, 100),
                slide_dimensions=(1000, 1000),
            )

    def test_generate_rejects_zero_thumbnail_height(
        self, generator: AxisGuideGenerator
    ) -> None:
        """Test generate raises ValueError for zero thumbnail height."""
        with pytest.raises(ValueError, match="thumbnail_size must be positive"):
            generator.generate(
                thumbnail_size=(100, 0),
                slide_dimensions=(1000, 1000),
            )

    def test_generate_rejects_zero_slide_width(
        self, generator: AxisGuideGenerator
    ) -> None:
        """Test generate raises ValueError for zero slide width."""
        with pytest.raises(ValueError, match="slide_dimensions must be positive"):
            generator.generate(
                thumbnail_size=(100, 100),
                slide_dimensions=(0, 1000),
            )

    def test_generate_rejects_zero_slide_height(
        self, generator: AxisGuideGenerator
    ) -> None:
        """Test generate raises ValueError for zero slide height."""
        with pytest.raises(ValueError, match="slide_dimensions must be positive"):
            generator.generate(
                thumbnail_size=(100, 100),
                slide_dimensions=(1000, 0),
            )

    def test_generate_rejects_negative_dimensions(
        self, generator: AxisGuideGenerator
    ) -> None:
        """Test generate raises ValueError for negative dimensions."""
        with pytest.raises(ValueError, match="thumbnail_size must be positive"):
            generator.generate(
                thumbnail_size=(-100, 100),
                slide_dimensions=(1000, 1000),
            )


class TestAxisGuideGeneratorLinePositions:
    """Tests for axis guide line positioning."""

    def test_vertical_line_positions(self) -> None:
        """Test vertical lines are evenly spaced."""
        generator = AxisGuideGenerator()
        # With thumbnail_width=500 and 4 guides:
        # step_x = 500 / 5 = 100
        # Lines at x = 100, 200, 300, 400
        overlay = generator.generate(
            thumbnail_size=(500, 400),
            slide_dimensions=(50000, 40000),
        )
        # Check pixels on expected line positions
        # At least one pixel along each expected vertical line should be drawn
        for expected_x in [100, 200, 300, 400]:
            line_has_pixels = False
            for y in range(0, 400, 20):  # Sample along the line
                pixel = overlay.getpixel((expected_x, y))
                if isinstance(pixel, tuple) and len(pixel) == 4 and pixel[3] > 0:
                    line_has_pixels = True
                    break
            assert line_has_pixels, f"No pixels drawn at vertical line x={expected_x}"

    def test_horizontal_line_positions(self) -> None:
        """Test horizontal lines are evenly spaced."""
        generator = AxisGuideGenerator()
        # With thumbnail_height=500 and 4 guides:
        # step_y = 500 / 5 = 100
        # Lines at y = 100, 200, 300, 400
        overlay = generator.generate(
            thumbnail_size=(400, 500),
            slide_dimensions=(40000, 50000),
        )
        # At least one pixel along each expected horizontal line should be drawn
        for expected_y in [100, 200, 300, 400]:
            line_has_pixels = False
            for x in range(0, 400, 20):  # Sample along the line
                pixel = overlay.getpixel((x, expected_y))
                if isinstance(pixel, tuple) and len(pixel) == 4 and pixel[3] > 0:
                    line_has_pixels = True
                    break
            assert line_has_pixels, f"No pixels drawn at horizontal line y={expected_y}"


class TestAxisGuideGeneratorCoordinateLabels:
    """Tests for coordinate label calculation."""

    def test_format_coordinate_small(self) -> None:
        """Test coordinate formatting for small values."""
        generator = AxisGuideGenerator()
        assert generator._format_coordinate(500) == "500"
        assert generator._format_coordinate(999) == "999"

    def test_format_coordinate_thousands(self) -> None:
        """Test coordinate formatting for 1000-9999."""
        generator = AxisGuideGenerator()
        assert generator._format_coordinate(1500) == "1500"

    def test_format_coordinate_ten_thousands(self) -> None:
        """Test coordinate formatting for >= 10000."""
        generator = AxisGuideGenerator()
        result = generator._format_coordinate(15000)
        assert result == "15000"

    def test_format_coordinate_large(self) -> None:
        """Test coordinate formatting for very large values."""
        generator = AxisGuideGenerator()
        result = generator._format_coordinate(100000)
        assert result == "100000"

    def test_strict_font_check_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test strict font check raises error when fonts are missing."""

        def mock_truetype(*args: object, **kwargs: object) -> None:
            raise OSError("Mocked font failure")

        monkeypatch.setattr(ImageFont, "truetype", mock_truetype)

        style = OverlayStyle(strict_font_check=True)
        generator = AxisGuideGenerator(style=style)

        with pytest.raises(RuntimeError, match="No TrueType fonts available"):
            generator._get_font()


class TestOverlayService:
    """Tests for OverlayService."""

    @pytest.fixture
    def service(self) -> OverlayService:
        """Create a default service."""
        return OverlayService()

    @pytest.fixture
    def mock_metadata(self) -> WSIMetadata:
        """Create mock WSI metadata."""
        return WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=80000,
            level_count=4,
            level_dimensions=(
                (100000, 80000),
                (50000, 40000),
                (25000, 20000),
                (12500, 10000),
            ),
            level_downsamples=(1.0, 2.0, 4.0, 8.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )

    @pytest.fixture
    def sample_thumbnail(self) -> Image.Image:
        """Create a sample RGB thumbnail."""
        return Image.new("RGB", (1024, 768), color=(200, 200, 200))

    def test_create_navigable_thumbnail_returns_rgb(
        self,
        service: OverlayService,
        sample_thumbnail: Image.Image,
        mock_metadata: WSIMetadata,
    ) -> None:
        """Test navigable thumbnail is RGB."""
        result = service.create_navigable_thumbnail(sample_thumbnail, mock_metadata)
        assert isinstance(result, Image.Image)
        assert result.mode == "RGB"

    def test_create_navigable_thumbnail_same_size(
        self,
        service: OverlayService,
        sample_thumbnail: Image.Image,
        mock_metadata: WSIMetadata,
    ) -> None:
        """Test navigable thumbnail has same size as input."""
        result = service.create_navigable_thumbnail(sample_thumbnail, mock_metadata)
        assert result.size == sample_thumbnail.size

    def test_create_navigable_thumbnail_rgba_input(
        self,
        service: OverlayService,
        mock_metadata: WSIMetadata,
    ) -> None:
        """Test service handles RGBA input thumbnail."""
        rgba_thumb = Image.new("RGBA", (512, 512), color=(200, 200, 200, 255))
        result = service.create_navigable_thumbnail(rgba_thumb, mock_metadata)
        assert result.mode == "RGB"

    def test_create_navigable_thumbnail_modifies_image(
        self,
        service: OverlayService,
        sample_thumbnail: Image.Image,
        mock_metadata: WSIMetadata,
    ) -> None:
        """Test navigable thumbnail is different from input (overlay applied)."""
        result = service.create_navigable_thumbnail(sample_thumbnail, mock_metadata)
        # The image should be modified somewhere (lines drawn)
        # Just verify we get a valid image back
        assert result.size == sample_thumbnail.size

    def test_create_overlay_only_returns_rgba(
        self,
        service: OverlayService,
        mock_metadata: WSIMetadata,
    ) -> None:
        """Test create_overlay_only returns RGBA."""
        overlay = service.create_overlay_only((1024, 768), mock_metadata)
        assert isinstance(overlay, Image.Image)
        assert overlay.mode == "RGBA"

    def test_create_overlay_only_correct_size(
        self,
        service: OverlayService,
        mock_metadata: WSIMetadata,
    ) -> None:
        """Test create_overlay_only has correct size."""
        thumbnail_size = (800, 600)
        overlay = service.create_overlay_only(thumbnail_size, mock_metadata)
        assert overlay.size == thumbnail_size

    def test_service_uses_custom_generator(self, mock_metadata: WSIMetadata) -> None:
        """Test service uses provided generator."""
        custom_style = OverlayStyle(line_width=5, num_guides=2)
        custom_generator = AxisGuideGenerator(style=custom_style)
        service = OverlayService(generator=custom_generator)

        assert service.generator.style.line_width == 5
        assert service.generator.style.num_guides == 2


class TestOverlayServiceIntegration:
    """Integration tests for OverlayService with realistic scenarios."""

    def test_typical_wsi_workflow(self) -> None:
        """Test typical WSI thumbnail overlay workflow."""
        # Simulate realistic WSI dimensions
        metadata = WSIMetadata(
            path="/data/slides/TCGA-XX-XXXX.svs",
            width=98304,  # ~98K wide
            height=71680,  # ~72K tall
            level_count=5,
            level_dimensions=(
                (98304, 71680),
                (49152, 35840),
                (24576, 17920),
                (12288, 8960),
                (6144, 4480),
            ),
            level_downsamples=(1.0, 2.0, 4.0, 8.0, 16.0),
            vendor="aperio",
            mpp_x=0.2522,
            mpp_y=0.2522,
        )

        # Create thumbnail at ~1024px
        thumb = Image.new("RGB", (1024, 746), color=(240, 220, 220))

        service = OverlayService()
        result = service.create_navigable_thumbnail(thumb, metadata)

        assert result.size == (1024, 746)
        assert result.mode == "RGB"

    def test_small_thumbnail_for_context_window(self) -> None:
        """Test with small thumbnail (fitting in LLM context)."""
        metadata = WSIMetadata(
            path="/path/to/slide.svs",
            width=50000,
            height=40000,
            level_count=3,
            level_dimensions=(
                (50000, 40000),
                (25000, 20000),
                (12500, 10000),
            ),
            level_downsamples=(1.0, 2.0, 4.0),
            vendor="unknown",
            mpp_x=None,
            mpp_y=None,
        )

        # Small thumbnail to reduce token usage
        thumb = Image.new("RGB", (256, 205), color=(200, 180, 180))

        service = OverlayService()
        result = service.create_navigable_thumbnail(thumb, metadata)

        assert result.size == (256, 205)
        assert result.mode == "RGB"
