"""Tissue segmentation for WSI analysis (Spec-11).

Implements CLAM-style tissue segmentation using Otsu thresholding
and morphological operations.

Paper Reference: "Following prior work, we use the CLAM Python package
to segment the tissue on the slide before patching."
"""

from __future__ import annotations

from typing import Any, Literal

import cv2
import numpy as np
import numpy.typing as npt
from PIL import Image

from giant.vision.constants import MORPH_KERNEL_SIZE

# Supported backend types
BackendType = Literal["parity", "clam"]
SUPPORTED_BACKENDS: frozenset[str] = frozenset({"parity", "clam"})


class TissueSegmentor:
    """Tissue segmentation with CLAM or parity backend.

    The parity backend reimplements CLAM's tissue segmentation algorithm
    using Otsu thresholding on HSV saturation channel plus morphological
    closing to fill small holes.

    Attributes:
        backend: Segmentation backend ("parity" or "clam").
    """

    __slots__ = ("_backend", "_kernel")

    def __init__(self, backend: BackendType = "parity") -> None:
        """Initialize segmentor with specified backend.

        Args:
            backend: Segmentation backend. "parity" (default) uses a
                CLAM-compatible reimplementation. "clam" would use the
                actual CLAM library (not yet implemented).

        Raises:
            ValueError: If backend is not supported.
        """
        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unsupported backend '{backend}'. "
                f"Supported: {sorted(SUPPORTED_BACKENDS)}"
            )
        self._backend = backend
        # Pre-create morphological kernel for closing
        self._kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE),
        )

    @property
    def backend(self) -> str:
        """Return the segmentation backend name."""
        return self._backend

    def segment(self, image: Image.Image) -> npt.NDArray[Any]:
        """Segment tissue from background in an image.

        Uses Otsu thresholding on the HSV saturation channel, followed by
        morphological closing to fill small holes.

        Args:
            image: PIL Image in RGB mode (typically a WSI thumbnail).

        Returns:
            Binary mask as numpy array where True/1 = tissue, False/0 = background.
            Shape is (height, width).

        Raises:
            ValueError: If image is not in RGB mode.
        """
        if self._backend == "clam":
            raise NotImplementedError(
                "CLAM backend not yet implemented. Use 'parity' instead."
            )

        # Convert PIL Image to numpy array
        if image.mode != "RGB":
            # Try to convert, but warn about grayscale
            if image.mode == "L":
                raise ValueError(
                    "Grayscale images not supported. Please provide RGB image."
                )
            image = image.convert("RGB")

        arr = np.array(image)

        # Convert RGB to HSV
        hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)

        # Extract saturation channel (index 1)
        saturation = hsv[:, :, 1]

        # Apply Otsu thresholding on saturation
        # Tissue (stained) typically has higher saturation than background (white)
        _, mask = cv2.threshold(
            saturation,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

        # Morphological closing to fill small holes
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel)

        return mask


def segment_tissue(
    image: Image.Image,
    backend: BackendType = "parity",
) -> npt.NDArray[Any]:
    """Convenience function to segment tissue from an image.

    Args:
        image: PIL Image in RGB mode.
        backend: Segmentation backend ("parity" or "clam").

    Returns:
        Binary mask where True/1 = tissue, False/0 = background.
    """
    segmentor = TissueSegmentor(backend=backend)
    return segmentor.segment(image)
