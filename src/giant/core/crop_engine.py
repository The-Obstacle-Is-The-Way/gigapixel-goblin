"""Image cropping and resampling pipeline for GIANT.

This module implements the CropRegion(W, at, S) function from Algorithm 1,
orchestrating WSIReader and PyramidLevelSelector to efficiently retrieve
a region of interest, resize it to exact target dimensions using high-quality
resampling, and format it for LMM consumption (Base64).

Paper Reference:
    Algorithm 1 defines CropRegion(W, at, S) which:
    1. Selects optimal pyramid level
    2. Reads region at that level
    3. Resizes to target_size preserving aspect ratio
    4. Encodes as Base64 JPEG for LMM input

Boundary Behavior:
    Regions extending beyond slide boundaries are handled gracefully via
    OpenSlide's native padding behavior. Out-of-bounds pixels are filled
    with transparency (RGBA), which becomes black after RGB conversion.
    This is the canonical behavior for boundary crops and is tested in
    integration tests (P1-1, P1-2). No clamping is performed at this layer;
    bounds validation/clamping can be applied at the agent layer (Spec-09).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from giant.core.level_selector import LevelSelectorProtocol, PyramidLevelSelector
from giant.geometry import Region
from giant.wsi.types import WSIReaderProtocol, size_at_level

# JPEG quality bounds (PIL accepts 1-100)
_JPEG_QUALITY_MIN = 1
_JPEG_QUALITY_MAX = 100

# Maximum pixel dimension for safety (prevents OOM on huge region requests)
# 10000 x 10000 RGBA = 400MB; this is a reasonable default upper bound.
# Can be overridden via max_read_dimension parameter in crop().
_DEFAULT_MAX_READ_DIMENSION = 10000


@dataclass(frozen=True)
class CroppedImage:
    """Result of cropping and resampling a WSI region.

    This immutable container holds the processed image along with metadata
    about the extraction process, useful for debugging and caching.

    Attributes:
        image: PIL Image in RGB mode, resized to target dimensions.
        base64_content: Base64-encoded JPEG representation for LMM input.
        original_region: The requested Level-0 region (input to crop).
        read_level: Pyramid level from which the image was read.
        scale_factor: Ratio of final dimensions to read dimensions.
            scale_factor < 1.0 means downsampling occurred after read.
            scale_factor = 1.0 means no resize (region smaller than target).
    """

    image: Image.Image
    base64_content: str
    original_region: Region
    read_level: int
    scale_factor: float


class CropEngine:
    """Orchestrates region extraction, resampling, and encoding for LMMs.

    The CropEngine implements the paper's CropRegion(W, at, S) function,
    coordinating between WSIReader for data access and PyramidLevelSelector
    for optimal level selection.

    Algorithm:
        1. Level Selection: Uses PyramidLevelSelector to find the optimal
           pyramid level that minimizes I/O while meeting target resolution.
        2. Read: Extracts the region at the selected level via WSIReader.
        3. Resize: Scales the image so long-side equals target_size,
           preserving aspect ratio, using LANCZOS resampling.
           Never upsamples - if read size < target, returns at read size.
        4. Encode: Converts to Base64 JPEG (quality=85 default).

    Example:
        >>> from giant.wsi import WSIReader
        >>> from giant.geometry import Region
        >>>
        >>> with WSIReader("slide.svs") as reader:
        ...     engine = CropEngine(reader)
        ...     region = Region(x=10000, y=20000, width=5000, height=4000)
        ...     result = engine.crop(region, target_size=1000)
        ...     print(f"Read from level {result.read_level}")
        ...     # result.base64_content ready for LMM
    """

    __slots__ = ("_level_selector", "_reader")

    def __init__(
        self,
        reader: WSIReaderProtocol,
        level_selector: LevelSelectorProtocol | None = None,
    ) -> None:
        """Initialize the crop engine.

        Args:
            reader: WSI reader implementing WSIReaderProtocol.
            level_selector: Optional level selector. If not provided,
                defaults to PyramidLevelSelector with standard parameters.
        """
        self._reader = reader
        self._level_selector = level_selector or PyramidLevelSelector()

    def crop(
        self,
        region: Region,
        target_size: int = 1000,
        bias: float = 0.85,
        jpeg_quality: int = 85,
        max_read_dimension: int | None = None,
    ) -> CroppedImage:
        """Extract, resize, and encode a region from the WSI.

        Implements the complete CropRegion(W, at, S) function from Algorithm 1.

        Args:
            region: Requested crop in Level-0 coordinates.
            target_size: Target long-side in pixels (default: 1000).
            bias: Oversampling bias for level selection (default: 0.85).
            jpeg_quality: JPEG encoding quality 1-100 (default: 85).
            max_read_dimension: Maximum allowed dimension (width or height) for
                the read operation, in pixels. If the region at the selected
                level exceeds this, a ValueError is raised to prevent OOM.
                Defaults to 10000 if not specified. Set to 0 (or negative) to
                disable the check.

        Returns:
            CroppedImage containing the processed image and metadata.

        Note:
            The algorithm invariant is preserved: we only downsample (or 1:1)
            to reach target_size. We never upsample; if the read region is
            smaller than target_size, it is returned unchanged.

        Raises:
            ValueError: If jpeg_quality is not in range 1-100.
            ValueError: If region at selected level exceeds max_read_dimension.
        """
        if not _JPEG_QUALITY_MIN <= jpeg_quality <= _JPEG_QUALITY_MAX:
            raise ValueError(
                f"jpeg_quality must be {_JPEG_QUALITY_MIN}-{_JPEG_QUALITY_MAX}, "
                f"got {jpeg_quality}"
            )

        # Step 1: Get metadata and select optimal level
        metadata = self._reader.get_metadata()
        selected = self._level_selector.select_level(
            region, metadata, target_size=target_size, bias=bias
        )

        # Step 2: Calculate size at selected level and read
        # Using size_at_level utility ensures min 1px per dimension
        region_size_at_level = size_at_level(
            (region.width, region.height), selected.downsample
        )

        # Memory safety: reject regions that would allocate too much memory
        # Use default if not specified; 0 disables the check
        effective_max = (
            _DEFAULT_MAX_READ_DIMENSION
            if max_read_dimension is None
            else max_read_dimension
        )
        max_dim = max(region_size_at_level)
        if effective_max > 0 and max_dim > effective_max:
            w, h = region_size_at_level
            raise ValueError(
                f"Region too large: {w}x{h} pixels at level {selected.level} "
                f"exceeds maximum dimension {effective_max}px. "
                f"Use a smaller region or get_thumbnail() for full-slide overview."
            )

        raw_image = self._reader.read_region(
            location=(region.x, region.y),
            level=selected.level,
            size=region_size_at_level,
        )

        # Step 3: Resize to target dimensions (never upsample)
        resized_image, scale_factor = self._resize_to_target(raw_image, target_size)

        # Step 4: Encode to Base64 JPEG
        base64_content = self._encode_base64_jpeg(resized_image, jpeg_quality)

        return CroppedImage(
            image=resized_image,
            base64_content=base64_content,
            original_region=region,
            read_level=selected.level,
            scale_factor=scale_factor,
        )

    def _resize_to_target(
        self,
        image: Image.Image,
        target_size: int,
    ) -> tuple[Image.Image, float]:
        """Resize image so long-side equals target_size exactly.

        Preserves aspect ratio. Never upsamples - if image is smaller
        than target_size, returns original image unchanged.

        Args:
            image: PIL Image to resize.
            target_size: Target long-side in pixels.

        Returns:
            Tuple of (resized_image, scale_factor).
            scale_factor is final_long_side / original_long_side.
        """
        original_width, original_height = image.size
        original_long_side = max(original_width, original_height)

        # Never upsample: if image is smaller than target, return as-is
        if original_long_side <= target_size:
            return image, 1.0

        # Calculate scale factor
        scale_factor = target_size / original_long_side

        # Compute new dimensions, ensuring long side is exactly target_size
        # This avoids floating-point truncation errors
        if original_width >= original_height:
            # Width is the long side
            new_width = target_size
            new_height = max(1, round(original_height * scale_factor))
        else:
            # Height is the long side
            new_height = target_size
            new_width = max(1, round(original_width * scale_factor))

        resized = image.resize(
            (new_width, new_height),
            resample=Image.Resampling.LANCZOS,
        )

        return resized, scale_factor

    def _encode_base64_jpeg(
        self,
        image: Image.Image,
        quality: int,
    ) -> str:
        """Encode image as Base64 JPEG.

        Args:
            image: PIL Image to encode.
            quality: JPEG quality 1-100.

        Returns:
            Standard Base64-encoded string (no URL-safe, no newlines).
        """
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
