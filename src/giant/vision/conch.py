"""CONCH tool interface (paper ablation feature).

The GIANT paper includes an ablation where the agent can invoke CONCH to score
image-text alignment between the current view (thumbnail/crop) and a set of
textual hypotheses. This module defines a minimal interface that the agent can
depend on without hard-coding CONCH implementation details or weight access.

The default implementation is intentionally unconfigured: CONCH weights are
gated and not bundled with this repo. Users can provide their own scorer
implementation via `AgentConfig.conch_scorer`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PIL import Image


class ConchUnavailableError(RuntimeError):
    """Raised when CONCH is requested but no scorer is configured."""


class ConchScorer(Protocol):
    """Protocol for scoring hypotheses against an image using CONCH."""

    def score_hypotheses(
        self, image: Image.Image, hypotheses: list[str]
    ) -> list[float]:
        """Score each hypothesis against the image.

        Args:
            image: PIL image of the current observation (thumbnail or crop).
            hypotheses: List of text hypotheses to score.

        Returns:
            List of floats aligned to the input hypotheses (same length).
        """


class UnconfiguredConchScorer:
    """A scorer that always raises, used as a clear default."""

    def score_hypotheses(
        self, image: Image.Image, hypotheses: list[str]
    ) -> list[float]:
        raise ConchUnavailableError(
            "CONCH scoring was requested but no conch_scorer is configured. "
            "Provide an implementation via AgentConfig.conch_scorer."
        )
