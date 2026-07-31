from pathlib import Path

import pytest

from word_madness_bot.domain.errors import ImageDecodeError
from word_madness_bot.vision.preprocessing import load_image, preprocess

FIXTURE = Path(__file__).parents[2] / "fixtures" / "images" / "shapes.png"


def test_load_and_preprocess_are_deterministic() -> None:
    image = load_image(FIXTURE)
    assert image.size == (32, 20)
    assert preprocess(image).tobytes() == preprocess(image).tobytes()


@pytest.mark.parametrize("source", [b"", b"invalid", Path("missing.png")])
def test_invalid_sources_are_typed(source: bytes | Path) -> None:
    with pytest.raises(ImageDecodeError):
        load_image(source)
