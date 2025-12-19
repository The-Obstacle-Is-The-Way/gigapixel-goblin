"""Constants for vision module (Spec-11).

Paper Reference: "Following prior work, we sample 30 random 224x224 patches."
"""

from __future__ import annotations

# Number of random patches to sample per slide (paper default)
N_PATCHES: int = 30

# Patch size in Level-0 pixels (paper default)
PATCH_SIZE: int = 224

# Default thumbnail size for tissue segmentation
# Roughly ~32x downsample from typical WSI dimensions
DEFAULT_THUMBNAIL_SIZE: tuple[int, int] = (2048, 2048)

# Morphological kernel size for closing operation
MORPH_KERNEL_SIZE: int = 5

# Minimum tissue area threshold (pixels in thumbnail space)
MIN_TISSUE_AREA: int = 100
