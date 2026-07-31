"""Tests for replaceable OCR and confidence-aware level reading."""

import numpy as np

from word_madness_bot.domain.models import OcrResult, ScreenGeometry
from word_madness_bot.vision.level_reader import LevelReader
from word_madness_bot.vision.ocr import TesseractOcrEngine
from word_madness_bot.vision.preprocessing import ImageArray


class StubOcr:
    """Deterministic OCR test double."""

    def __init__(self, result: OcrResult | None) -> None:
        self.result = result
        self.whitelist: str | None = None

    def recognize(self, image: ImageArray, *, whitelist: str | None = None) -> OcrResult | None:
        """Return the configured result and record the requested alphabet."""

        self.whitelist = whitelist
        return self.result


def test_level_reader_returns_number_and_confidence() -> None:
    """Digit OCR is converted into a typed, confidence-bearing reading."""

    ocr = StubOcr(OcrResult("90", 0.87))
    reader = LevelReader(ocr)
    image = np.zeros((1000, 500, 3), dtype=np.uint8)

    result = reader.read(image, ScreenGeometry(500, 1000, 320))

    assert result is not None
    assert (result.number, result.confidence) == (90, 0.87)
    assert ocr.whitelist == "0123456789"


def test_level_reader_rejects_low_confidence() -> None:
    """OCR below policy threshold does not become a level observation."""

    reader = LevelReader(StubOcr(OcrResult("90", 0.2)))

    assert (
        reader.read(np.zeros((100, 100, 3), dtype=np.uint8), ScreenGeometry(100, 100, 320)) is None
    )


def test_tesseract_tsv_parser_aggregates_word_confidence() -> None:
    """The concrete adapter parses stable TSV output without OCR-process coupling."""

    header = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
        "left\ttop\twidth\theight\tconf\ttext"
    )
    row = "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t92.0\t90"

    result = TesseractOcrEngine._parse_tsv(f"{header}\n{row}\n")

    assert result == OcrResult("90", 0.92)
