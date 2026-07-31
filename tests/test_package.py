"""Production package smoke tests."""

from pathlib import Path

import word_madness_bot


def test_production_package_imports_from_src_layout() -> None:
    package_path = Path(word_madness_bot.__file__).resolve()

    assert package_path.parent.name == "word_madness_bot"
    assert package_path.parent.parent.name == "src"
    assert word_madness_bot.__version__ == "0.1.0"
