"""Release-level assertion that multi-level integration coverage remains available."""

from pathlib import Path


def test_multi_level_integration_scenario_is_part_of_release_suite() -> None:
    scenario = Path(__file__).resolve().parents[1] / "integration/gameplay/test_complete_level.py"
    text = scenario.read_text(encoding="utf-8")
    assert "test_multiple_consecutive_levels_submit_each_word_once" in text
