"""Tests for normalized, confidence-bearing template matching."""

import numpy as np

from word_madness_bot.domain.models import BoundingBox
from word_madness_bot.vision.template_matcher import TemplateMatcher


def test_template_match_returns_exact_absolute_location() -> None:
    """A nonconstant template is located relative to its search region."""

    image = np.zeros((40, 50, 3), dtype=np.uint8)
    template = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    image[17:19, 23:25, :] = template[..., None]

    match = TemplateMatcher().match(
        image,
        template,
        BoundingBox(10, 10, 40, 30),
        minimum_confidence=0.99,
    )

    assert match is not None
    assert match.region == BoundingBox(23, 17, 25, 19)
    assert match.confidence == 1.0


def test_template_match_respects_threshold() -> None:
    """Weak evidence is returned as no match rather than an unsafe guess."""

    image = np.zeros((10, 10), dtype=np.uint8)
    template = np.full((3, 3), 255, dtype=np.uint8)

    assert (
        TemplateMatcher().match(image, template, BoundingBox(0, 0, 10, 10), minimum_confidence=0.9)
        is None
    )
