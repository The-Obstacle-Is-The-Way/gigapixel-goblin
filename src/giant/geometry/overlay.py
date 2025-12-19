"""Axis guide overlay generation for GIANT.

This module implements the visual axis guides overlaid on WSI thumbnails
to help the LLM orient itself during navigation. As specified in the GIANT
paper: "Thumbnail is overlaid with four evenly spaced axis guides along
each dimension, labeled with absolute level-0 pixel coordinates."

The overlay provides spatial reference by drawing grid lines at regular
intervals and labeling them with their corresponding Level-0 coordinates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from giant.wsi.types import WSIMetadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverlayStyle:
    """Configuration for axis guide visual styling.

    Attributes:
        line_color: RGBA color for grid lines.
        line_width: Width of grid lines in pixels.
        label_color: RGBA color for coordinate labels.
        font_size: Font size for coordinate labels.
        label_padding: Padding from edge for labels in pixels.
        num_guides: Number of guide lines per axis (default 4).
        strict_font_check: If True, raise error if no TrueType font is found.
    """

    line_color: tuple[int, int, int, int] = (255, 0, 0, 180)  # Semi-transparent red
    line_width: int = 2
    label_color: tuple[int, int, int, int] = (255, 255, 255, 255)  # White
    font_size: int = 12
    label_padding: int = 5
    num_guides: int = 4
    strict_font_check: bool = False


class AxisGuideGenerator:
    """Generates axis guide overlays for WSI thumbnails.

    Creates transparent overlay images with evenly spaced grid lines
    and Level-0 coordinate labels. The overlay can be composited onto
    thumbnails to help LLMs understand spatial positioning.

    The generator follows the GIANT paper specification:
    - 4 evenly spaced guides per axis (configurable)
    - Labels showing absolute Level-0 pixel coordinates
    - Semi-transparent styling to avoid obscuring tissue
    """

    def __init__(self, style: OverlayStyle | None = None) -> None:
        """Initialize the generator with optional custom styling.

        Args:
            style: Visual styling configuration. Uses defaults if not provided.
        """
        self.style = style or OverlayStyle()

    def generate(
        self,
        thumbnail_size: tuple[int, int],
        slide_dimensions: tuple[int, int],
    ) -> Image.Image:
        """Generate an axis guide overlay image.

        Creates a transparent RGBA image with grid lines and coordinate
        labels that can be composited onto a thumbnail.

        Args:
            thumbnail_size: (width, height) of the thumbnail in pixels.
            slide_dimensions: (width, height) of the slide at Level-0.

        Returns:
            RGBA PIL Image with the axis guide overlay.

        Raises:
            ValueError: If thumbnail_size or slide_dimensions contain
                non-positive values.
            RuntimeError: If strict_font_check is True and no valid font found.

        Example:
            >>> generator = AxisGuideGenerator()
            >>> overlay = generator.generate(
            ...     thumbnail_size=(1024, 768),
            ...     slide_dimensions=(100000, 75000),
            ... )
            >>> overlay.mode
            'RGBA'
        """
        # Validate inputs to prevent division by zero
        if thumbnail_size[0] <= 0 or thumbnail_size[1] <= 0:
            raise ValueError(f"thumbnail_size must be positive, got {thumbnail_size}")
        if slide_dimensions[0] <= 0 or slide_dimensions[1] <= 0:
            raise ValueError(
                f"slide_dimensions must be positive, got {slide_dimensions}"
            )

        thumb_w, thumb_h = thumbnail_size
        slide_w, slide_h = slide_dimensions

        # Create transparent overlay
        overlay = Image.new("RGBA", thumbnail_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Calculate scale factors for coordinate conversion
        # thumbnail coord -> Level-0 coord
        scale_x = slide_w / thumb_w
        scale_y = slide_h / thumb_h

        # Load font (fallback to default if not available)
        font = self._get_font()

        # Calculate step sizes to get num_guides internal lines
        # Dividing by (num_guides + 1) creates num_guides evenly spaced internal lines
        step_x = thumb_w / (self.style.num_guides + 1)
        step_y = thumb_h / (self.style.num_guides + 1)

        # Draw vertical lines and labels
        for i in range(1, self.style.num_guides + 1):
            x = int(step_x * i)
            l0_x = int(x * scale_x)

            # Draw vertical line
            draw.line(
                [(x, 0), (x, thumb_h)],
                fill=self.style.line_color,
                width=self.style.line_width,
            )

            # Draw label at top of line
            label = self._format_coordinate(l0_x)
            self._draw_label(
                draw,
                label,
                (x, self.style.label_padding),
                font,
                anchor="mt",  # middle-top
            )

        # Draw horizontal lines and labels
        for i in range(1, self.style.num_guides + 1):
            y = int(step_y * i)
            l0_y = int(y * scale_y)

            # Draw horizontal line
            draw.line(
                [(0, y), (thumb_w, y)],
                fill=self.style.line_color,
                width=self.style.line_width,
            )

            # Draw label at left of line
            label = self._format_coordinate(l0_y)
            self._draw_label(
                draw,
                label,
                (self.style.label_padding, y),
                font,
                anchor="lm",  # left-middle
            )

        return overlay

    def _get_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Get font for labels, with fallback to default.

        Returns:
            Font object for drawing text.

        Raises:
            RuntimeError: If strict_font_check is True and no TrueType font found.
        """
        try:
            # Try to load a common sans-serif font
            return ImageFont.truetype("DejaVuSans.ttf", self.style.font_size)
        except OSError:
            try:
                # Try Arial on Windows/Mac
                return ImageFont.truetype("Arial.ttf", self.style.font_size)
            except OSError:
                if self.style.strict_font_check:
                    raise RuntimeError(
                        "No TrueType fonts available (DejaVuSans.ttf, Arial.ttf). "
                        "Strict font check is enabled. Install system fonts."
                    ) from None
                # Fall back to PIL's default font
                logger.warning(
                    "No TrueType fonts available (DejaVuSans.ttf, Arial.ttf). "
                    "Using low-resolution default font. Install fonts for better "
                    "quality."
                )
                return ImageFont.load_default()

    def _format_coordinate(self, coord: int) -> str:
        """Format a coordinate value for display.

        Uses absolute integer coordinates as per GIANT paper.

        Args:
            coord: Coordinate value in pixels.

        Returns:
            Formatted string representation (e.g., "15000").
        """
        return str(coord)

    def _draw_label(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple[int, int],
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        anchor: str,
    ) -> None:
        """Draw a label with background for visibility.

        Args:
            draw: ImageDraw object to draw on.
            text: Label text to draw.
            position: (x, y) position for the label.
            font: Font to use for rendering.
            anchor: Pillow text anchor (e.g., "mt" for middle-top).
        """
        # Draw text with slight shadow for visibility
        x, y = position
        shadow_color = (0, 0, 0, 200)

        # Shadow offset
        for dx, dy in [(1, 1), (-1, -1), (1, -1), (-1, 1)]:
            draw.text(
                (x + dx, y + dy),
                text,
                fill=shadow_color,
                font=font,
                anchor=anchor,
            )

        # Main text
        draw.text(
            position,
            text,
            fill=self.style.label_color,
            font=font,
            anchor=anchor,
        )


class OverlayService:
    """Service for combining thumbnails with axis guide overlays.

    This service orchestrates the creation of navigable thumbnail images
    by compositing axis guides onto WSI thumbnails. It handles the
    coordination between thumbnail generation and overlay creation.
    """

    def __init__(
        self,
        generator: AxisGuideGenerator | None = None,
    ) -> None:
        """Initialize the service with an optional custom generator.

        Args:
            generator: AxisGuideGenerator to use. Creates default if not provided.
        """
        self.generator = generator or AxisGuideGenerator()

    def create_navigable_thumbnail(
        self,
        thumbnail: Image.Image,
        metadata: WSIMetadata,
    ) -> Image.Image:
        """Create a thumbnail with axis guide overlay.

        Composites the axis guide overlay onto the thumbnail to create
        an image suitable for LLM navigation.

        Args:
            thumbnail: RGB thumbnail image of the WSI.
            metadata: WSI metadata containing slide dimensions.

        Returns:
            RGB image with axis guides overlaid.

        Example:
            >>> service = OverlayService()
            >>> with WSIReader("slide.svs") as reader:
            ...     thumb = reader.get_thumbnail((1024, 1024))
            ...     metadata = reader.get_metadata()
            ...     navigable = service.create_navigable_thumbnail(thumb, metadata)
        """
        # Generate the overlay
        overlay = self.generator.generate(
            thumbnail_size=thumbnail.size,
            slide_dimensions=(metadata.width, metadata.height),
        )

        # Convert thumbnail to RGBA for compositing
        if thumbnail.mode != "RGBA":
            thumb_rgba = thumbnail.convert("RGBA")
        else:
            thumb_rgba = thumbnail

        # Composite overlay onto thumbnail
        composited = Image.alpha_composite(thumb_rgba, overlay)

        # Convert back to RGB for output
        return composited.convert("RGB")

    def create_overlay_only(
        self,
        thumbnail_size: tuple[int, int],
        metadata: WSIMetadata,
    ) -> Image.Image:
        """Create just the overlay without compositing.

        Useful for debugging or custom compositing pipelines.

        Args:
            thumbnail_size: (width, height) of the target thumbnail.
            metadata: WSI metadata containing slide dimensions.

        Returns:
            RGBA image with just the axis guides.
        """
        return self.generator.generate(
            thumbnail_size=thumbnail_size,
            slide_dimensions=(metadata.width, metadata.height),
        )
