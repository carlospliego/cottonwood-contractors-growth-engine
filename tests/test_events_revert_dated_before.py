# sir-target: tests/test_events_revert_dated_before.py
"""A reverting correction dated before the lead's latest stage change is refused (F-correctness-4).

The revert it would write is a stage change at the correction's time; if that is earlier than
the latest effective stage change (a revert counts), leads.stage and history ordered by
occurred_at would disagree.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Lead 1 (inbound, candidate): call 09:30 -> contacted, walkthrough 09:45 -> walkthrough."""
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    args = ["--channel", "form", "--received", "2026-11-15 08:00", "--segment", "commercial"]
    assert main(["log-inbound", "--db", str(path), *args, "--name", "Pat Lee"]) == EXIT_OK
    for event, at, stage in (
        ("call", "2026-11-16 09:30", "contacted_or_replied"),
        ("walkthrough", "2026-11-16 09:45", "walkthrough"),
    ):
        code = main(["log-event", "--db", str(path), "1", event, "--at", at, "--stage", stage])
        assert code == EXIT_OK
    return path


def _id(db_path: Path, activity_type: str) -> str:
    conn = sqlite3.connect(db_path)
    try:
        sql = "SELECT max(id) FROM activities WHERE type = ?"
        return str(conn.execute(sql, (activity_type,)).fetchone()[0])
    finally:
        conn.close()


def _state(db_path: Path) -> tuple[int, str]:
    conn = sqlite3.connect(db_path)
    try:
        count = int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
        stage = str(conn.execute("SELECT stage FROM leads WHERE id = 1").fetchone()[0])
    finally:
        conn.close()
    return count, stage


def _void(db_path: Path, target: str, at: str) -> int:
    return main(
        ["log-event", "--db", str(db_path), "1", "correction", "--voids", target, "--at", at]
    )


def test_revert_dated_before_an_earlier_revert_exits_1_and_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Voiding the walkthrough at 10:30 writes a revert (walkthrough -> contacted) at 10:30.
    assert _void(db_path, _id(db_path, "walkthrough"), "2026-11-16 10:30") == EXIT_OK
    before = _state(db_path)
    assert before[1] == "contacted_or_replied"
    capsys.readouterr()

    # Voiding the call at 10:00 would revert contacted -> candidate at 10:00, before 10:30.
    assert _void(db_path, _id(db_path, "call"), "2026-11-16 10:00") == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: at:")
    assert "latest stage change" in err
    assert _state(db_path) == before


def test_revert_dated_before_the_change_it_undoes_is_already_refused(db_path: Path) -> None:
    # A correction must follow its target; the walkthrough (and its change) is at 09:45.
    before = _state(db_path)
    assert _void(db_path, _id(db_path, "walkthrough"), "2026-11-16 09:40") == EXIT_REFUSED
    assert _state(db_path) == before


def test_revert_at_or_after_the_latest_stage_change_is_saved(db_path: Path) -> None:
    assert _void(db_path, _id(db_path, "walkthrough"), "2026-11-16 10:30") == EXIT_OK
    # At the same time as the earlier revert: it ranks after it by id, so it is allowed.
    assert _void(db_path, _id(db_path, "call"), "2026-11-16 10:30") == EXIT_OK
    assert _state(db_path)[1] == "candidate"


def test_correction_of_an_event_without_a_stage_is_not_affected(db_path: Path) -> None:
    assert _void(db_path, _id(db_path, "walkthrough"), "2026-11-16 10:30") == EXIT_OK
    code = main(
        ["log-event", "--db", str(db_path), "1", "acknowledgement", "--at", "2026-11-16 09:50"]
    )
    assert code == EXIT_OK
    # Voiding a stageless event writes no revert, so its time is only bound by its target.
    assert _void(db_path, _id(db_path, "acknowledgement"), "2026-11-16 10:00") == EXIT_OK
