"""Replaceable OCR abstraction and a subprocess-backed Tesseract adapter."""

import logging
import subprocess
from io import BytesIO
from typing import Protocol

from PIL import Image

from word_madness_bot.domain.models import OcrResult
from word_madness_bot.vision.preprocessing import ImageArray

_LOGGER = logging.getLogger(__name__)


class OcrEngine(Protocol):
    """Recognize text without exposing a concrete OCR implementation."""

    def recognize(self, image: ImageArray, *, whitelist: str | None = None) -> OcrResult | None:
        """Return recognized text and confidence, or ``None`` when recognition fails."""

        ...


class TesseractOcrEngine:
    """Invoke Tesseract through its stable command-line boundary."""

    def __init__(
        self,
        command: str = "tesseract",
        language: str = "eng",
        timeout_seconds: float = 10.0,
        page_segmentation_mode: int = 7,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("OCR timeout must be positive")
        self._command = command
        self._language = language
        self._timeout_seconds = timeout_seconds
        self._page_segmentation_mode = page_segmentation_mode

    def recognize(self, image: ImageArray, *, whitelist: str | None = None) -> OcrResult | None:
        """Recognize image text and average valid Tesseract word confidences."""

        buffer = BytesIO()
        Image.fromarray(image).save(buffer, format="PNG")
        command = [
            self._command,
            "stdin",
            "stdout",
            "--psm",
            str(self._page_segmentation_mode),
            "-l",
            self._language,
        ]
        if whitelist:
            command.extend(["-c", f"tessedit_char_whitelist={whitelist}"])
        command.append("tsv")
        try:
            completed = subprocess.run(
                command,
                input=buffer.getvalue(),
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            _LOGGER.warning("OCR command is unavailable: %s", self._command)
            return None
        except subprocess.TimeoutExpired:
            _LOGGER.warning("OCR command timed out after %.1f seconds", self._timeout_seconds)
            return None
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            _LOGGER.warning("OCR command failed with code %d: %s", completed.returncode, stderr)
            return None
        return self._parse_tsv(completed.stdout.decode("utf-8", errors="replace"))

    @staticmethod
    def _parse_tsv(tsv: str) -> OcrResult | None:
        lines = tsv.splitlines()
        if len(lines) < 2:
            return None
        words: list[str] = []
        confidences: list[float] = []
        for line in lines[1:]:
            fields = line.split("\t", maxsplit=11)
            if len(fields) != 12 or not fields[11].strip():
                continue
            try:
                confidence = float(fields[10])
            except ValueError:
                continue
            if confidence < 0:
                continue
            words.append(fields[11].strip())
            confidences.append(confidence / 100.0)
        if not words:
            return None
        return OcrResult(text=" ".join(words), confidence=sum(confidences) / len(confidences))
