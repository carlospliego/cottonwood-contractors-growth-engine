# sir-target: tests/test_default_config_path.py
"""Without --config or $COTTONWOOD_CONFIG, backup reads config/pilot.yaml (F-testing-3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config, db
from cottonwood.cli import main


def test_backup_uses_config_pilot_yaml_from_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(config.CONFIG_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    live = tmp_path / "live.db"
    db.migrate(live)
    target = tmp_path / "from-default-config"
    target.mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "pilot.yaml").write_text(
        f'paths:\n  backup_dir: "{target}"\n', encoding="utf-8"
    )

    assert config.default_config_path() == Path("config/pilot.yaml")
    assert main(["backup", "--db", str(live)]) == 0

    written = list(target.iterdir())
    assert len(written) == 1, written
    assert written[0].name.startswith("cottonwood-") and written[0].suffix == ".db"
    assert f"backup written: {written[0]}" in capsys.readouterr().out
