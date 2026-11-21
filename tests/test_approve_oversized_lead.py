# sir-target: tests/test_approve_oversized_lead.py
"""approve refuses a lead id SQLite cannot hold, instead of crashing (R-18).

F-correctness-2: 'approve lead N' and '--lead N' bound N straight into a query, so an N above
9223372036854775807 raised OverflowError with a traceback instead of 'error: lead:'.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
TOO_LARGE = "99999999999999999999"  # above SQLite's 64-bit integer ceiling, 2**63 - 1


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _activity_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
    finally:
        conn.close()


def _refused(db_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> list[str]:
    capsys.readouterr()
    command = ["approve", *args, "--approver", "Founder", "--reference", "r", "--db", str(db_path)]
    assert main(command) == EXIT_REFUSED
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert _activity_count(db_path) == 0
    return captured.err.splitlines()


@pytest.mark.parametrize("lead", [TOO_LARGE, str(2**63)])
def test_approve_lead_with_an_oversized_id_is_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str], lead: str
) -> None:
    lines = _refused(db_path, capsys, "lead", lead)
    assert lines == [f"error: lead: no lead {lead}"]


@pytest.mark.parametrize("lead", [TOO_LARGE, str(2**63), str(-(2**63) - 1)])
def test_an_oversized_lead_option_is_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str], lead: str
) -> None:
    lines = _refused(db_path, capsys, "offer", "x", "--lead", lead)
    assert lines == [f"error: lead: no lead {lead}"]


def test_the_largest_sqlite_id_is_still_looked_up(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = _refused(db_path, capsys, "lead", str(2**63 - 1))
    assert lines == [f"error: lead: no lead {2**63 - 1}"]
