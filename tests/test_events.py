"""Tests for log-event: recording R-15 events on a lead (R-15, AC-1.x, AC-6.1)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, EXIT_USAGE, main

AT = "2026-11-16 09:30"
AT_UTC = "2026-11-16T16:30:00Z"
# The spec's example time may be later than the real clock, so "now" is pinned after it.
NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
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
    return main(["log-event", "--db", str(db_path), *args])


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _activity_count(db_path: Path) -> int:
    return int(_rows(db_path, "SELECT count(*) FROM activities")[0][0])


def _stage(db_path: Path) -> str:
    return str(_rows(db_path, "SELECT stage FROM leads WHERE id = 1")[0][0])


def _events(db_path: Path) -> list[sqlite3.Row]:
    return _rows(db_path, "SELECT * FROM activities WHERE type <> 'inquiry_logged' ORDER BY id")


def test_event_types_match_r15() -> None:
    assert events.EVENT_TYPES == (
        "acknowledgement",
        "call",
        "missed_call",
        "call_returned",
        "remote_screen",
        "walkthrough",
        "proposal",
        "won",
        "lost",
        "partner_conversation",
        "handoff",
        "note",
    )


@pytest.mark.parametrize("event_type", events.EVENT_TYPES)
def test_each_type_appends_one_activity(db_path: Path, event_type: str) -> None:
    extra = ["--note", "spoke briefly"] if event_type == "note" else []
    before = _activity_count(db_path)
    assert _event(db_path, "1", event_type, "--at", AT, *extra) == EXIT_OK
    assert _activity_count(db_path) == before + 1
    rows = _events(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["lead_id"] == 1
    assert row["type"] == event_type
    assert row["occurred_at"] == AT_UTC
    assert row["actor"] == "developer"
    assert row["recorded_at"]
    assert row["voids_activity_id"] is None
    assert json.loads(row["payload"])["event"] == event_type
    assert _stage(db_path) == "candidate"


def test_actor_option_is_stored(db_path: Path) -> None:
    assert _event(db_path, "1", "call", "--at", AT, "--actor", "founder") == EXIT_OK
    assert _events(db_path)[0]["actor"] == "founder"


def test_blank_actor_is_refused(db_path: Path) -> None:
    assert _event(db_path, "1", "call", "--at", AT, "--actor", "  ") == EXIT_REFUSED
    assert _events(db_path) == []


def test_utc_at_is_stored_as_given(db_path: Path) -> None:
    assert _event(db_path, "1", "call", "--at", AT_UTC) == EXIT_OK
    assert _events(db_path)[0]["occurred_at"] == AT_UTC


def test_missing_at_is_a_usage_error(db_path: Path) -> None:
    assert _event(db_path, "1", "call") == EXIT_USAGE
    assert _events(db_path) == []


@pytest.mark.parametrize("bad", ["tomorrow", "2026-13-01 09:00", "2026-11-16 9:30", ""])
def test_unparseable_at_is_refused(
    db_path: Path, bad: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _event(db_path, "1", "call", "--at", bad) == EXIT_REFUSED
    assert "error: at:" in capsys.readouterr().err
    assert _events(db_path) == []


@pytest.mark.parametrize("future", ["2999-01-01 00:00", "2999-01-01T00:00:00Z"])
def test_future_at_is_refused(
    db_path: Path, future: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _event(db_path, "1", "call", "--at", future) == EXIT_REFUSED
    assert "error: at:" in capsys.readouterr().err
    assert _events(db_path) == []


def test_validate_event_refuses_time_after_now() -> None:
    raw = events.RawEvent(lead_id=1, type="call", at="2026-11-16T16:30:01Z")
    with pytest.raises(events.EventError):
        events.validate_event(raw, "2026-11-16T16:30:00Z")
    ok = events.validate_event(raw, "2026-11-16T16:30:01Z")
    assert ok.occurred_at == "2026-11-16T16:30:01Z"


@pytest.mark.parametrize("bad_type", ["bogus", "stage_change", "Call"])
def test_unknown_type_is_a_usage_error(db_path: Path, bad_type: str) -> None:
    assert _event(db_path, "1", bad_type, "--at", AT) == EXIT_USAGE
    assert _events(db_path) == []


def test_unknown_lead_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before = _activity_count(db_path)
    assert _event(db_path, "999", "call", "--at", AT) == EXIT_REFUSED
    assert "error: no lead 999" in capsys.readouterr().err
    assert _activity_count(db_path) == before


@pytest.mark.parametrize("note", [None, "", "   "])
def test_note_type_needs_note_text(db_path: Path, note: str | None) -> None:
    args = ["1", "note", "--at", AT]
    if note is not None:
        args += ["--note", note]
    assert _event(db_path, *args) == EXIT_REFUSED
    assert _events(db_path) == []


def test_note_text_is_stored_on_other_types(db_path: Path) -> None:
    assert _event(db_path, "1", "call", "--at", AT, "--note", "  left a voicemail ") == EXIT_OK
    assert json.loads(_events(db_path)[0]["payload"]) == {
        "event": "call",
        "note": "left a voicemail",
    }


def test_payload_has_no_note_key_without_note(db_path: Path) -> None:
    assert _event(db_path, "1", "acknowledgement", "--at", AT) == EXIT_OK
    assert json.loads(_events(db_path)[0]["payload"]) == {"event": "acknowledgement"}


def test_success_line_names_activity_type_lead_and_local_time(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert _event(db_path, "1", "walkthrough", "--at", AT) == EXIT_OK
    out = capsys.readouterr().out
    activity_id = _events(db_path)[0]["id"]
    assert f"activity {activity_id}" in out
    assert "walkthrough" in out
    assert "lead 1" in out
    assert timeutil.display_local(AT_UTC) in out
    assert "2026-11-16 09:30 -07:00" in out


def test_missing_database_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope.db"
    assert main(["log-event", "--db", str(missing), "1", "call", "--at", AT]) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert not missing.exists()


def test_unmigrated_database_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    assert main(["log-event", "--db", str(empty), "1", "call", "--at", AT]) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    conn = sqlite3.connect(empty)
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()
    assert tables == []
