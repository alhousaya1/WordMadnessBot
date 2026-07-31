from PIL import Image

from word_madness_bot.vision.templates import TemplateMatcher


def test_threshold_no_match_and_multiple_matches() -> None:
    image = Image.new("L", (8, 4), 0)
    for x in (0, 4):
        image.paste(Image.new("L", (2, 2), 255), (x, 1))
    template = Image.new("L", (2, 2), 255)
    assert len(TemplateMatcher(threshold=1).match(image, template, label="tile")) == 2
    assert TemplateMatcher(threshold=1).match(image, Image.new("L", (2, 2), 127), label="x") == ()
