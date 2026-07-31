"""Static release checks for packaging and runtime dependency consistency."""

import tomllib
from pathlib import Path


def test_runtime_requirements_match_project_dependencies() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    declared = set(project["project"]["dependencies"])
    requirements = {
        line.strip()
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert requirements == declared


def test_package_declares_console_entry_point_and_runtime_data() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["word-madness-bot"] == "word_madness_bot.cli:main"
    data_files = project["tool"]["setuptools"]["data-files"]
    assert "database/levels.json" in data_files["database"]
    assert "templates/manifest.json" in data_files["templates"]
