# sir-target: tests/test_config_backup_dir.py
"""paths.backup_dir expands ~ and trims surrounding spaces (F-correctness-6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config


def _load(tmp_path: Path, backup_dir: str) -> config.Config:
    path = tmp_path / "config.yaml"
    path.write_text(f'paths:\n  backup_dir: "{backup_dir}"\n', encoding="utf-8")
    return config.load_config(path)


def test_tilde_expands_to_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert _load(tmp_path, "~/b").backup_dir == tmp_path / "b"


def test_surrounding_spaces_are_trimmed(tmp_path: Path) -> None:
    assert _load(tmp_path, " data/backups ").backup_dir == Path("data/backups")
