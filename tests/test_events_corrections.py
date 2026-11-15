"""Tests for corrections: voiding events, stage reverts and the counted-activity rule (R-17)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
T1 = "2026-11-16 09:30"
T2 = "2026-11-16 09:45"
T_FIX = "2026-11-16 10:00"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Lead 1 and lead 2: inbound (candidate). Lead 3: test inbound lead."""
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    for name, email, extra in (
        ("Pat Lee", "pat@example.com", []),
        ("Sam Roe", "sam@example.com", []),
        ("Test Person", "test@example.com", ["--test"]),
    ):
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
                name,
                "--email",
                email,
                *extra,
            ]
        )
        assert code == EXIT_OK
    return path


def _main(db_path: Path, *args: str) -> int:
    return main(["log-event", "--db", str(db_path), *args])


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _last_id(db_path: Path, activity_type: str) -> int:
    return int(
        _rows(db_path, "SELECT max(id) FROM activities WHERE type = ?", (activity_type,))[0][0]
    )


def _stage(db_path: Path, lead_id: int = 1) -> str:
    return str(_rows(db_path, "SELECT stage FROM leads WHERE id = ?", (lead_id,))[0][0])


def _count(db_path: Path) -> int:
    return int(_rows(db_path, "SELECT count(*) FROM activities")[0][0])


def _counted_ids(db_path: Path) -> list[int]:
    conn = db.connect(db_path)
    try:
        return [int(r["id"]) for r in events.counted_activities(conn)]
    finally:
        conn.close()


def _row(db_path: Path, activity_id: int) -> tuple[object, ...]:
    return tuple(_rows(db_path, "SELECT * FROM activities WHERE id = ?", (activity_id,))[0])


def test_correction_appends_one_row_and_leaves_target_untouched(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _main(db_path, "1", "call", "--at", T1) == EXIT_OK
    call_id = _last_id(db_path, "call")
    before_row = _row(db_path, call_id)
    before = _count(db_path)
    capsys.readouterr()
    assert (
        _main(db_path, "1", "correction", "--voids", str(call_id), "--at", T_FIX, "--note", "typo")
        == EXIT_OK
    )
    assert _count(db_path) == before + 1
    rows = _rows(db_path, "SELECT * FROM activities WHERE type = 'correction'")
    assert len(rows) == 1
    fix = rows[0]
    assert fix["lead_id"] == 1
    assert fix["voids_activity_id"] == call_id
    assert fix["occurred_at"] == "2026-11-16T17:00:00Z"
    assert json.loads(fix["payload"]) == {"note": "typo"}
    assert _row(db_path, call_id) == before_row
    out = capsys.readouterr().out
    assert f"voids activity {call_id}" in out
    assert "stage" not in out


def test_counted_activities_drop_voided_event_correction_and_its_stage_change(
    db_path: Path,
) -> None:
    assert _main(db_path, "1", "acknowledgement", "--at", T1) == EXIT_OK
    ack_id = _last_id(db_path, "acknowledgement")
    assert _main(db_path, "1", "call", "--at", T2, "--stage", "contacted_or_replied") == EXIT_OK
    call_id = _last_id(db_path, "call")
    change_id = _last_id(db_path, "stage_change")
    assert {ack_id, call_id, change_id} <= set(_counted_ids(db_path))
    assert _main(db_path, "1", "correction", "--voids", str(call_id), "--at", T_FIX) == EXIT_OK
    fix_id = _last_id(db_path, "correction")
    counted = set(_counted_ids(db_path))
    assert call_id not in counted
    assert change_id not in counted
    assert fix_id not in counted
    assert ack_id in counted
    conn = db.connect(db_path)
    try:
        calls = events.counted_activities(conn, "call")
        acks = events.counted_activities(conn, "acknowledgement")
    finally:
        conn.close()
    assert calls == []
    assert [int(r["id"]) for r in acks] == [ack_id]


def test_voiding_latest_stage_event_reverts_the_stage(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _main(db_path, "1", "call", "--at", T1, "--stage", "contacted_or_replied") == EXIT_OK
    assert _main(db_path, "1", "walkthrough", "--at", T2, "--stage", "walkthrough") == EXIT_OK
    walk_id = _last_id(db_path, "walkthrough")
    capsys.readouterr()
    assert _main(db_path, "1", "correction", "--voids", str(walk_id), "--at", T_FIX) == EXIT_OK
    assert _stage(db_path) == "contacted_or_replied"
    fix_id = _last_id(db_path, "correction")
    revert = _rows(db_path, "SELECT * FROM activities WHERE type = 'stage_change' ORDER BY id")[-1]
    assert json.loads(revert["payload"]) == {
        "from": "walkthrough",
        "to": "contacted_or_replied",
        "event_activity_id": fix_id,
    }
    assert revert["occurred_at"] == "2026-11-16T17:00:00Z"
    assert revert["id"] not in _counted_ids(db_path)
    assert "stage walkthrough -> contacted_or_replied" in capsys.readouterr().out
    # The earlier change is now the latest effective one, so it can be reverted in turn.
    call_id = _last_id(db_path, "call")
    assert _main(db_path, "1", "correction", "--voids", str(call_id), "--at", T_FIX) == EXIT_OK
    assert _stage(db_path) == "candidate"


def test_voiding_an_older_stage_event_is_refused_naming_the_later_change(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _main(db_path, "1", "call", "--at", T1, "--stage", "contacted_or_replied") == EXIT_OK
    call_id = _last_id(db_path, "call")
    assert _main(db_path, "1", "walkthrough", "--at", T2, "--stage", "walkthrough") == EXIT_OK
    later_change = _last_id(db_path, "stage_change")
    before = _count(db_path)
    capsys.readouterr()
    assert _main(db_path, "1", "correction", "--voids", str(call_id), "--at", T_FIX) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert f"activity {later_change}" in err
    assert _count(db_path) == before
    assert _stage(db_path) == "walkthrough"


def test_same_time_changes_are_ordered_by_id(db_path: Path) -> None:
    assert _main(db_path, "1", "call", "--at", T1, "--stage", "researched") == EXIT_OK
    first = _last_id(db_path, "call")
    assert _main(db_path, "1", "remote_screen", "--at", T1, "--stage", "walkthrough") == EXIT_OK
    second = _last_id(db_path, "remote_screen")
    before = _count(db_path)
    assert _main(db_path, "1", "correction", "--voids", str(first), "--at", T_FIX) == EXIT_REFUSED
    assert _count(db_path) == before
    assert _main(db_path, "1", "correction", "--voids", str(second), "--at", T_FIX) == EXIT_OK
    assert _stage(db_path) == "researched"


def test_event_without_stage_change_can_be_voided_any_time(db_path: Path) -> None:
    assert _main(db_path, "1", "missed_call", "--at", T1) == EXIT_OK
    missed = _last_id(db_path, "missed_call")
    assert _main(db_path, "1", "call", "--at", T2, "--stage", "contacted_or_replied") == EXIT_OK
    assert _main(db_path, "1", "correction", "--voids", str(missed), "--at", T_FIX) == EXIT_OK
    assert _stage(db_path) == "contacted_or_replied"


def _refused(db_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> None:
    before = _count(db_path)
    stage = _stage(db_path)
    capsys.readouterr()
    assert _main(db_path, *args) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")
    assert _count(db_path) == before
    assert _stage(db_path) == stage


def test_refusals_write_nothing(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _main(db_path, "1", "call", "--at", T1, "--stage", "researched") == EXIT_OK
    call_id = _last_id(db_path, "call")
    change_id = _last_id(db_path, "stage_change")
    inquiry_id = int(
        _rows(db_path, "SELECT id FROM activities WHERE type = 'inquiry_logged' AND lead_id = 1")[
            0
        ][0]
    )
    assert _main(db_path, "2", "call", "--at", T1) == EXIT_OK
    other_lead_call = _last_id(db_path, "call")
    # --voids missing
    _refused(db_path, capsys, "1", "correction", "--at", T_FIX)
    # no such activity
    _refused(db_path, capsys, "1", "correction", "--voids", "9999", "--at", T_FIX)
    # another lead's activity
    _refused(db_path, capsys, "1", "correction", "--voids", str(other_lead_call), "--at", T_FIX)
    # not an R-15 event
    _refused(db_path, capsys, "1", "correction", "--voids", str(change_id), "--at", T_FIX)
    _refused(db_path, capsys, "1", "correction", "--voids", str(inquiry_id), "--at", T_FIX)
    # --stage (and the R-16 flags) with a correction
    _refused(
        db_path, capsys, "1", "correction", "--voids", str(call_id), "--at", T_FIX, "--stage", "won"
    )
    _refused(
        db_path, capsys, "1", "correction", "--voids", str(call_id), "--at", T_FIX, "--need", "x"
    )
    # earlier than the event it voids
    _refused(
        db_path, capsys, "1", "correction", "--voids", str(call_id), "--at", "2026-11-16 09:00"
    )
    # voiding a correction, then an already-void event
    assert _main(db_path, "1", "correction", "--voids", str(call_id), "--at", T_FIX) == EXIT_OK
    fix_id = _last_id(db_path, "correction")
    _refused(db_path, capsys, "1", "correction", "--voids", str(fix_id), "--at", T_FIX)
    _refused(db_path, capsys, "1", "correction", "--voids", str(call_id), "--at", T_FIX)
    # --voids on a non-correction type
    _refused(db_path, capsys, "1", "call", "--at", T_FIX, "--voids", str(call_id))


def test_unknown_lead_correction_is_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _count(db_path)
    assert _main(db_path, "999", "correction", "--voids", "1", "--at", T_FIX) == EXIT_REFUSED
    assert "error: no lead 999" in capsys.readouterr().err
    assert _count(db_path) == before


def test_test_lead_activities_are_not_counted(db_path: Path) -> None:
    assert _main(db_path, "3", "call", "--at", T1, "--stage", "researched") == EXIT_OK
    assert _main(db_path, "1", "call", "--at", T1) == EXIT_OK
    conn = db.connect(db_path)
    try:
        counted = events.counted_activities(conn)
    finally:
        conn.close()
    assert counted
    assert all(row["lead_id"] != 3 for row in counted)
    test_ids = {int(r[0]) for r in _rows(db_path, "SELECT id FROM activities WHERE lead_id = 3")}
    assert test_ids
    assert not test_ids & {int(r["id"]) for r in counted}


def test_failed_revert_rolls_back(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _main(db_path, "1", "call", "--at", T1, "--stage", "researched") == EXIT_OK
    call_id = _last_id(db_path, "call")
    conn = db.connect(db_path)
    try:
        conn.execute(
            "CREATE TRIGGER fail_revert BEFORE INSERT ON activities"
            " WHEN NEW.type = 'stage_change' BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
        conn.commit()
    finally:
        conn.close()
    before = _count(db_path)
    assert _main(db_path, "1", "correction", "--voids", str(call_id), "--at", T_FIX) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert _count(db_path) == before
    assert _stage(db_path) == "researched"
