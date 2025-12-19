"""Tissue segmentation for WSI analysis (Spec-11).

Implements CLAM-style tissue segmentation using Otsu thresholding
and morphological operations.

Paper Reference: "Following prior work, we use the CLAM Python package
to segment the tissue on the slide before patching."
"""

from __future__ import annotations

from typing import Literal, cast

import cv2
import numpy as np
import numpy.typing as npt
from PIL import Image

from giant.vision.constants import MIN_TISSUE_AREA, MORPH_KERNEL_SIZE

# Supported backend types
BackendType = Literal["parity", "clam"]
SUPPORTED_BACKENDS: frozenset[str] = frozenset({"parity", "clam"})


class TissueSegmentor:
    """Tissue segmentation with CLAM or parity backend.

    The segmentation algorithm is CLAM-compatible: Otsu thresholding on
    the HSV saturation channel, morphological closing to fill small holes,
    and removal of small connected components.

    Notes:
        The `clam` backend name is reserved for a future optional integration
        with the external CLAM library. Today, both `clam` and `parity` run
        the same CLAM-parity implementation to keep behavior portable.

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

    def segment(self, image: Image.Image) -> npt.NDArray[np.bool_]:
        """Segment tissue from background in an image.

        Uses Otsu thresholding on the HSV saturation channel, followed by
        morphological closing to fill small holes, and removal of small
        connected components.

        Args:
            image: PIL Image in RGB mode (typically a WSI thumbnail).

        Returns:
            Boolean mask where True = tissue, False = background.
            Shape is (height, width).

        Raises:
            ValueError: If image is not in RGB mode.
        """
        # Convert PIL Image to numpy array
        if image.mode != "RGB":
            # Reject grayscale, but try to convert other modes
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
        mask_uint8 = cast(npt.NDArray[np.uint8], mask.astype(np.uint8, copy=False))
        mask_uint8 = cast(
            npt.NDArray[np.uint8],
            cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, self._kernel),
        )

        mask_uint8 = self._remove_small_components(mask_uint8)

        return mask_uint8 > 0

    @staticmethod
    def _remove_small_components(mask: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
        """Remove tiny foreground components to reduce sampling noise."""
        num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
        if num_labels <= 1:
            return mask

        for label in range(1, num_labels):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < MIN_TISSUE_AREA:
                mask[labels == label] = 0

        return mask


def segment_tissue(
    image: Image.Image,
    backend: BackendType = "parity",
) -> npt.NDArray[np.bool_]:
    """Convenience function to segment tissue from an image.

    Args:
        image: PIL Image in RGB mode.
        backend: Segmentation backend ("parity" or "clam").

    Returns:
        Boolean mask where True = tissue, False = background.
    """
    segmentor = TissueSegmentor(backend=backend)
    return segmentor.segment(image)
