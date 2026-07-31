import pytest

from word_madness_bot.vision.classifier import VisionClassifier


def test_classifier_confidence_and_unknown() -> None:
    classifier = VisionClassifier(minimum_confidence=0.8)
    assert classifier.classify({"screen-a": 0.9, "screen-b": 0.7}).label == "screen-a"
    assert classifier.classify({"screen-a": 0.79}).label == "unknown"
    assert classifier.classify({}).confidence == 0


def test_classifier_rejects_invalid_evidence() -> None:
    with pytest.raises(ValueError):
        VisionClassifier().classify({"bad": 1.1})


def test_vision_package_does_not_import_android_input() -> None:
    import word_madness_bot.vision as vision

    assert not any("adb" in name.lower() or "android" in name.lower() for name in vision.__dict__)
