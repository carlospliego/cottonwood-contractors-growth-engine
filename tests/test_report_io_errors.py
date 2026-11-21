# sir-target: tests/test_report_io_errors.py
"""Tests for report's I/O failure branches: unreadable database and unwritable --out (R-28)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    return path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def test_out_write_failure_exits_1(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a regular file", encoding="utf-8")
    out = blocker / "report.md"
    code = main(["report", "--db", str(db_path), "--period", "7d", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error: could not write")
    assert "Traceback" not in captured.err
    assert "report written" not in captured.out
    assert blocker.read_text(encoding="utf-8") == "a regular file"


def test_database_read_failure_exits_1(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(report, "build_report", boom)
    out = tmp_path / "out" / "report.md"
    code = main(["report", "--db", str(db_path), "--period", "7d", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error: could not read the database:")
    assert "database is locked" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert not out.exists()
