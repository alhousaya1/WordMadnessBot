"""Unit tests for bounded configuration-controlled artifact storage."""

from pathlib import Path

from word_madness_bot.observability.artifacts import ArtifactManager


def test_disabled_manager_has_no_filesystem_side_effect(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path / "artifacts", enabled=False)
    assert manager.save("frame.png", b"data") is None
    assert not (tmp_path / "artifacts").exists()


def test_safe_filename_and_file_count_retention(tmp_path: Path) -> None:
    directory = tmp_path / "artifacts"
    manager = ArtifactManager(directory, enabled=True, maximum_files=2)
    manager.save("../first.bin", b"one")
    manager.save("second.bin", b"two")
    manager.save("third.bin", b"three")
    assert sorted(path.name for path in directory.iterdir()) == ["second.bin", "third.bin"]


def test_byte_retention_removes_oldest_artifacts(tmp_path: Path) -> None:
    directory = tmp_path / "artifacts"
    manager = ArtifactManager(directory, enabled=True, maximum_bytes=5)
    manager.save("one.bin", b"1234")
    manager.save("two.bin", b"5678")
    assert [path.name for path in directory.iterdir()] == ["two.bin"]
