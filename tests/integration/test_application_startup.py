from __future__ import annotations

import subprocess
import sys

from word_madness_bot.cli import main


def test_production_dry_run_starts_without_device_io() -> None:
    assert main(["--dry-run"], environ={}) == 0


def test_module_entry_point_help_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "word_madness_bot", "--help"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0
    assert "--dry-run" in result.stdout
