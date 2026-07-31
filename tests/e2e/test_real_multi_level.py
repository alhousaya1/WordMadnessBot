"""Opt-in physical-device acceptance test for consecutive autonomous levels."""

import os

import pytest

from word_madness_bot.bootstrap import build_application


@pytest.mark.skipif(
    os.environ.get("WORD_MADNESS_RUN_DEVICE_E2E") != "1",
    reason="set WORD_MADNESS_RUN_DEVICE_E2E=1 with a prepared authorized device",
)
def test_autonomous_runtime_advances_across_two_real_levels() -> None:
    """Run bounded autonomous cycles and prove that the observed level advances twice."""

    expected_start = int(os.environ["WORD_MADNESS_E2E_START_LEVEL"])
    expected_end = int(os.environ["WORD_MADNESS_E2E_END_LEVEL"])
    maximum_cycles = int(os.environ.get("WORD_MADNESS_E2E_MAXIMUM_CYCLES", "200"))
    if expected_end < expected_start + 2:
        pytest.fail("WORD_MADNESS_E2E_END_LEVEL must be at least two levels after start")

    app = build_application()
    initial = app.observe_once()
    assert initial.level is not None and initial.level.number == expected_start
    app.run_continuous(maximum_cycles=maximum_cycles)
    final = app.observe_once()
    assert final.level is not None and final.level.number >= expected_end
