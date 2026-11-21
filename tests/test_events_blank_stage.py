# sir-target: tests/test_events_blank_stage.py
"""A blank --stage on log-event is refused, not read as "no move" (F-maintainability-4)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
AT = "2026-11-16 09:30"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    args = ["--channel", "phone", "--received", "2026-11-15 08:00", "--segment", "commercial"]
    assert main(["log-inbound", "--db", str(path), *args, "--name", "Pat Lee"]) == EXIT_OK
    return path


def _state(db_path: Path) -> tuple[int, str]:
    conn = sqlite3.connect(db_path)
    try:
        count = int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
        stage = str(conn.execute("SELECT stage FROM leads WHERE id = 1").fetchone()[0])
    finally:
        conn.close()
    return count, stage


def _event(db_path: Path, *extra: str) -> int:
    return main(["log-event", "--db", str(db_path), "1", "call", "--at", AT, *extra])


@pytest.mark.parametrize("stage", [" ", "", "\t", "   "])
def test_blank_stage_exits_1_and_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str], stage: str
) -> None:
    before = _state(db_path)
    capsys.readouterr()

    assert _event(db_path, "--stage", stage) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: stage: must not be blank")
    assert _state(db_path) == before


def test_no_stage_still_logs_the_event_without_a_move(db_path: Path) -> None:
    count, stage = _state(db_path)
    assert _event(db_path) == EXIT_OK
    assert _state(db_path) == (count + 1, stage)
