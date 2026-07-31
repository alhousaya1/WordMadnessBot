"""Single composition root for concrete production dependencies."""

from word_madness_bot.adapters.adb import AdbCommandExecutor, AdbInputExecutor, AdbRuntimeAdapter
from word_madness_bot.adapters.database import JsonLevelRepository
from word_madness_bot.application import Application, ApplicationDependencies
from word_madness_bot.config import Settings
from word_madness_bot.domain.enums import VisionEvidenceKind
from word_madness_bot.domain.models import (
    CapturedFrame,
    RuntimeObservation,
    SwipeLetter,
    VisionEvidence,
)
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy
from word_madness_bot.gameplay.decision_engine import DecisionEngine
from word_madness_bot.gameplay.level_solver import LevelSolver
from word_madness_bot.gameplay.progress import LevelProgress
from word_madness_bot.gameplay.recovery_policy import RecoveryPolicy
from word_madness_bot.gameplay.state_machine import DecisionStateMachine
from word_madness_bot.state.classifier import StateClassifier
from word_madness_bot.state.stabilizer import StateStabilizer
from word_madness_bot.swipe.path_planner import PathPlanner
from word_madness_bot.vision.circle_detector import CircleDetector
from word_madness_bot.vision.debug_renderer import DebugRenderer
from word_madness_bot.vision.geometry import to_normalized_point
from word_madness_bot.vision.letter_extractor import LetterExtractor
from word_madness_bot.vision.level_reader import LevelReader
from word_madness_bot.vision.ocr import TesseractOcrEngine
from word_madness_bot.vision.preprocessing import decode_frame
from word_madness_bot.vision.wheel_reader import WheelReader


class ProductionObservationPipeline:
    """Compose existing Vision and State components without gameplay decisions."""

    def __init__(self, settings: Settings) -> None:
        ocr = TesseractOcrEngine()
        self._level_reader = LevelReader(ocr)
        self._wheel_reader = WheelReader(
            CircleDetector(),
            LetterExtractor(ocr),
            DebugRenderer(settings),
        )
        self._state = StateClassifier.from_settings(settings)
        self._stabilizer = StateStabilizer.from_settings(settings)

    def observe(self, frame: CapturedFrame, revision: int) -> RuntimeObservation:
        """Produce one typed observation from existing component outputs."""

        image = decode_frame(frame)
        level = self._level_reader.read(image, frame.geometry)
        wheel = self._wheel_reader.read(image, frame.geometry)
        evidence: list[VisionEvidence] = []
        letters: tuple[SwipeLetter, ...] = ()
        if level is not None:
            evidence.append(VisionEvidence(VisionEvidenceKind.LEVEL_NUMBER, level.confidence))
        if wheel is not None:
            evidence.append(VisionEvidence(VisionEvidenceKind.LETTER_WHEEL, wheel.confidence))
            letters = tuple(
                SwipeLetter(letter.character, to_normalized_point(letter.center, frame.geometry))
                for letter in wheel.letters
            )
        state = self._stabilizer.stabilize(self._state.classify(evidence))
        return RuntimeObservation(revision, state, level, letters)


def build_application(settings: Settings | None = None) -> Application:
    """Wire every production component in the repository's single composition root."""

    configured = settings or Settings.from_environment()
    repository = JsonLevelRepository(configured.level_database_file)
    adb_commands = AdbCommandExecutor(configured.adb_command, configured.adb_timeout_seconds)
    adb = AdbRuntimeAdapter(adb_commands)
    inputs = AdbInputExecutor(adb_commands, adb)
    state = StateClassifier.from_settings(configured)
    solver = LevelSolver(
        repository,
        PathPlanner.from_settings(configured),
        LevelProgress(),
        maximum_word_attempts=configured.word_max_attempts,
    )
    engine = DecisionEngine(
        state,
        solver,
        AdvertisementPolicy.from_settings(configured),
        RecoveryPolicy.from_settings(configured),
        DecisionStateMachine(),
    )
    return Application(
        ApplicationDependencies(
            settings=configured,
            repository=repository,
            devices=adb,
            capture=adb,
            inputs=inputs,
            observations=ProductionObservationPipeline(configured),
            decision_engine=engine,
        )
    )
