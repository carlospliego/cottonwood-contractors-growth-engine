# sir-target: tests/test_events_backdated_stage.py
"""A stage change dated before the lead's latest effective one is refused (CCGE-060).

Chosen behavior: refuse, so leads.stage always equals the latest effective stage change by
(occurred_at, id), and a correction never reverts to a stage a backdated event replaced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
CALL_AT_0945 = ("call", "--at", "2026-11-16 09:45", "--stage", "contacted_or_replied")


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Lead 1: an inbound lead at candidate."""
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    code = main(
        [
            "log-inbound",
            "--db",
            str(path),
            "--channel",
            "form",
            "--received",
            "2026-11-15 08:00",
            "--segment",
            "commercial",
            "--name",
            "Pat Lee",
        ]
    )
    assert code == EXIT_OK
    return path


def _event(db_path: Path, *args: str) -> int:
    return main(["log-event", "--db", str(db_path), "1", *args])


def _one(db_path: Path, sql: str) -> object:
    conn = db.connect(db_path)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def _stage(db_path: Path) -> str:
    return str(_one(db_path, "SELECT stage FROM leads WHERE id = 1"))


def _activities(db_path: Path) -> int:
    return int(str(_one(db_path, "SELECT count(*) FROM activities")))


def _last(db_path: Path, activity_type: str) -> int:
    return int(str(_one(db_path, f"SELECT max(id) FROM activities WHERE type = '{activity_type}'")))


def test_backdated_stage_change_exits_1_and_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _event(db_path, *CALL_AT_0945) == EXIT_OK
    call_id = _last(db_path, "call")
    before = _activities(db_path)
    capsys.readouterr()

    code = _event(db_path, "walkthrough", "--at", "2026-11-16 09:30", "--stage", "walkthrough")

    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    assert "at" in err
    assert "latest stage change" in err
    assert "Traceback" not in err
    assert _activities(db_path) == before
    assert _stage(db_path) == "contacted_or_replied"

    # The stage and the latest effective stage change still agree, so voiding the call
    # reverts to the stage before it.
    assert _event(db_path, "correction", "--voids", str(call_id), "--at", "2026-11-16 10:00") == 0
    assert _stage(db_path) == "candidate"


def test_stage_change_at_the_same_time_is_allowed(db_path: Path) -> None:
    assert _event(db_path, *CALL_AT_0945) == EXIT_OK
    assert _event(db_path, "walkthrough", "--at", "2026-11-16 09:45", "--stage", "walkthrough") == 0
    assert _stage(db_path) == "walkthrough"


def test_backdated_event_without_a_stage_is_allowed(db_path: Path) -> None:
    assert _event(db_path, *CALL_AT_0945) == EXIT_OK
    assert _event(db_path, "acknowledgement", "--at", "2026-11-16 09:00") == EXIT_OK
    assert _stage(db_path) == "contacted_or_replied"


def test_a_voided_stage_change_does_not_block_an_earlier_move(db_path: Path) -> None:
    assert _event(db_path, *CALL_AT_0945) == EXIT_OK
    call_id = _last(db_path, "call")
    assert _event(db_path, "correction", "--voids", str(call_id), "--at", "2026-11-16 10:00") == 0
    assert _stage(db_path) == "candidate"

    # Nothing effective is later now (the revert is not an event's move), so 09:30 is fine.
    assert _event(db_path, "walkthrough", "--at", "2026-11-16 09:30", "--stage", "walkthrough") == 0
    assert _stage(db_path) == "walkthrough"
    walk_id = _last(db_path, "walkthrough")
    assert _event(db_path, "correction", "--voids", str(walk_id), "--at", "2026-11-16 10:05") == 0
    assert _stage(db_path) == "candidate"
