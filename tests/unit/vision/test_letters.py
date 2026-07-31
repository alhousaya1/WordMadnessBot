from pathlib import Path

from word_madness_bot.vision.letters import detect_circles, extract_letters
from word_madness_bot.vision.preprocessing import load_image, preprocess

FIXTURE = Path(__file__).parents[2] / "fixtures" / "images" / "shapes.png"


def test_circle_detection_and_letter_extraction() -> None:
    image = load_image(FIXTURE)
    circles = detect_circles(preprocess(image))
    assert len(circles) == 2
    regions = extract_letters(image, circles)
    assert len(regions) == 2
    assert all(region.image.width > 0 for region in regions)


def test_blank_image_has_no_circles() -> None:
    assert (
        detect_circles(
            preprocess(load_image(Path(__file__).parents[2] / "fixtures" / "images" / "blank.png"))
        )
        == ()
    )
