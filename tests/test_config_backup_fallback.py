# sir-target: tests/test_config_backup_fallback.py
"""load_config falls back to data/backups and rejects an empty backup_dir (F-testing-2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config


def _load(tmp_path: Path, text: str) -> config.Config:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return config.load_config(path)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="empty-file"),
        pytest.param("paths:\n", id="paths-without-value"),
        pytest.param("paths:\n  other: x\n", id="mapping-without-backup_dir"),
    ],
)
def test_missing_backup_dir_falls_back_to_data_backups(tmp_path: Path, text: str) -> None:
    assert _load(tmp_path, text).backup_dir == Path("data/backups")


@pytest.mark.parametrize("value", [pytest.param("", id="empty"), pytest.param("  ", id="spaces")])
def test_empty_backup_dir_is_refused(tmp_path: Path, value: str) -> None:
    with pytest.raises(config.ConfigError, match="paths.backup_dir must be a non-empty string"):
        _load(tmp_path, f'paths:\n  backup_dir: "{value}"\n')
