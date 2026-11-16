# sir-target: tests/test_review_env_config_missing.py
"""A set-but-missing $COTTONWOOD_CONFIG must be an error, not an empty config."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config, db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main


def test_review_missing_env_config_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cottonwood.db"
    db.migrate(db_path)
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(tmp_path / "missing.yaml"))
    code = main(["review", "--db", str(db_path)])
    assert code == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")


def test_review_unset_env_and_missing_default_still_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "cottonwood.db"
    db.migrate(db_path)
    monkeypatch.delenv(config.CONFIG_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(["review", "--db", str(db_path)]) == EXIT_OK
