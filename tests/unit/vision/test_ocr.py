import pytest
from PIL import Image

from word_madness_bot.domain.errors import OcrError
from word_madness_bot.vision.ocr import OcrResult, recognize


class Fake:
    def __init__(self, value: object) -> None:
        self.value = value

    def recognize(self, image: Image.Image) -> OcrResult:
        if isinstance(self.value, Exception):
            raise self.value
        return self.value  # type: ignore[return-value]


def test_ocr_success() -> None:
    assert recognize(Fake(OcrResult(" A ", 0.9)), Image.new("L", (1, 1))).text == "A"


@pytest.mark.parametrize("value", [OcrResult("", 1), OcrResult("A", -1), object(), RuntimeError()])
def test_ocr_invalid_empty_malformed_and_failure(value: object) -> None:
    with pytest.raises(OcrError):
        recognize(Fake(value), Image.new("L", (1, 1)))
