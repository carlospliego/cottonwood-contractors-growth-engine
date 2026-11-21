"""log_event, log_correction and void_entry take the write lock before reading (F-correctness-1).

The refusal checks (already void, stage rules) and the inserts must see one state, so two
concurrent corrections cannot both void the same activity.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil

NOW = "2026-12-01T00:00:00Z"
AT = "2026-11-20 09:00"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _time_entry(db_path: Path) -> int:
    conn = db.connect(db_path)
    try:
        entry = events.TimeEntry(
            Decimal("1.5"), date(2026, 11, 20), "outreach", "founder", False, None, "founder"
        )
        return events.log_time(conn, entry)
    finally:
        conn.close()


def _lead(db_path: Path) -> int:
    conn = db.connect(db_path)
    try:
        lead_id = conn.execute(
            "INSERT INTO leads (type, stage) VALUES ('direct_candidate', 'candidate')"
        ).lastrowid
        conn.commit()
    finally:
        conn.close()
    assert lead_id is not None
    return lead_id


def _first(statements: list[str], prefix: str) -> int:
    return next(i for i, s in enumerate(statements) if s.lstrip().upper().startswith(prefix))


def _traced(db_path: Path) -> tuple[sqlite3.Connection, list[str]]:
    conn = db.connect(db_path)
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    return conn, statements


def test_second_void_is_refused_while_the_first_holds_the_lock(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry_id = _time_entry(db_path)
    first = db.connect(db_path)
    second = sqlite3.connect(db_path, timeout=0.05)
    second.row_factory = sqlite3.Row
    outcome: dict[str, object] = {}
    real = events._voided_by

    def while_first_holds_the_lock(conn: sqlite3.Connection, activity_id: int) -> int | None:
        result = real(conn, activity_id)
        if conn is first and "during" not in outcome:
            # The first void has read "not yet void" and holds the write lock: a concurrent
            # void of the same entry cannot get past its own BEGIN IMMEDIATE.
            try:
                events.void_entry(second, entry_id, events.TIME_KIND, "developer", NOW)
            except sqlite3.OperationalError as exc:
                outcome["during"] = str(exc)
            else:
                outcome["during"] = "saved"
        return result

    monkeypatch.setattr(events, "_voided_by", while_first_holds_the_lock)
    try:
        events.void_entry(first, entry_id, events.TIME_KIND, "founder", NOW)
        assert outcome["during"] == "database is locked"
        # After the first commits, the second sees the void and is refused.
        with pytest.raises(events.EventError, match="already void"):
            events.void_entry(second, entry_id, events.TIME_KIND, "developer", NOW)
    finally:
        first.close()
        second.close()
    conn = db.connect(db_path)
    try:
        voids = conn.execute(
            "SELECT count(*) FROM activities WHERE voids_activity_id = ?", (entry_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert voids == 1


def test_void_entry_locks_before_its_first_select(db_path: Path) -> None:
    entry_id = _time_entry(db_path)
    conn, statements = _traced(db_path)
    try:
        events.void_entry(conn, entry_id, events.TIME_KIND, "founder", NOW)
    finally:
        conn.close()
    assert _first(statements, "BEGIN IMMEDIATE") < _first(statements, "SELECT")


def test_log_event_locks_before_its_first_select(db_path: Path) -> None:
    lead_id = _lead(db_path)
    event = events.validate_event(events.RawEvent(lead_id=lead_id, type="call", at=AT), NOW)
    conn, statements = _traced(db_path)
    try:
        events.log_event(conn, event)
    finally:
        conn.close()
    assert _first(statements, "BEGIN IMMEDIATE") < _first(statements, "SELECT")


def test_log_correction_locks_before_its_first_select(db_path: Path) -> None:
    lead_id = _lead(db_path)
    conn = db.connect(db_path)
    try:
        event = events.validate_event(events.RawEvent(lead_id=lead_id, type="call", at=AT), NOW)
        logged = events.log_event(conn, event)
    finally:
        conn.close()
    correction = events.validate_correction(
        events.RawCorrection(lead_id=lead_id, voids_id=logged.event_id, at=AT), NOW
    )
    conn, statements = _traced(db_path)
    try:
        events.log_correction(conn, correction)
    finally:
        conn.close()
    assert _first(statements, "BEGIN IMMEDIATE") < _first(statements, "SELECT")
