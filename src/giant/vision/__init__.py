"""Vision module for tissue segmentation and patch sampling (Spec-11).

This module implements the CLAM-style tissue segmentation and random patch
sampling pipeline for the "Random Patch" baseline evaluation.
"""

from __future__ import annotations

from giant.vision.aggregation import aggregate_predictions
from giant.vision.constants import N_PATCHES, PATCH_SIZE
from giant.vision.sampler import RandomPatchSampler, sample_patches
from giant.vision.segmentation import TissueSegmentor

__all__ = [
    "N_PATCHES",
    "PATCH_SIZE",
    "RandomPatchSampler",
    "TissueSegmentor",
    "aggregate_predictions",
    "sample_patches",
]
