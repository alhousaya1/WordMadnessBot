"""State integration tests using the checked-in real screenshot fixture."""

from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from word_madness_bot.domain.enums import GameState, VisionEvidenceKind
from word_madness_bot.domain.models import CapturedFrame, ScreenGeometry, VisionEvidence
from word_madness_bot.state.classifier import StateClassifier
from word_madness_bot.state.evidence_collector import EvidenceCollector
from word_madness_bot.state.stabilizer import StateStabilizer
from word_madness_bot.vision.circle_detector import CircleDetector
from word_madness_bot.vision.preprocessing import decode_frame

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCREENSHOT = _PROJECT_ROOT / "tests" / "fixtures" / "screens" / "playing_level_90.png"


class FixtureVisionProvider:
    """Produce state evidence from the real frame using a Milestone 5 detector."""

    def collect_evidence(self, frame: CapturedFrame) -> tuple[VisionEvidence, ...]:
        """Translate a detected wheel into standardized Vision evidence."""

        circle = CircleDetector().detect(decode_frame(frame), frame.geometry)
        if circle is None:
            return ()
        return (VisionEvidence(VisionEvidenceKind.LETTER_WHEEL, circle.confidence),)


def _fixture_frame() -> CapturedFrame:
    with Image.open(_SCREENSHOT) as image:
        width, height = image.size
    return CapturedFrame(
        data=_SCREENSHOT.read_bytes(),
        geometry=ScreenGeometry(width, height, 600),
        captured_at=datetime.now(UTC),
    )


def test_real_playing_fixture_classifies_and_stabilizes() -> None:
    """Real Vision evidence deterministically reaches a stable PLAYING observation."""

    evidence = EvidenceCollector(FixtureVisionProvider()).collect(_fixture_frame())
    classified = StateClassifier().classify(evidence)
    stabilizer = StateStabilizer(required_consecutive=2)

    first = stabilizer.stabilize(classified)
    second = stabilizer.stabilize(classified)

    assert classified.state is GameState.PLAYING
    assert first.state is GameState.UNKNOWN
    assert second.state is GameState.PLAYING
    assert second.confidence > 0.9
