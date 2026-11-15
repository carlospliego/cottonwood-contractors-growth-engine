# sir-target: tests/test_events_void_definition.py
"""The R-17 "is this activity void" rule has one definition (F-maintainability-2).

Counting, the effective-stage-change check and both already-void refusals must all come
from the single fragment builder ``_voided_sql`` / ``_voiding_sql`` and the ``_voided_by``
helper, so changing void semantics in one place cannot leave a stale copy elsewhere.
"""

from __future__ import annotations

import inspect
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
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
    return db.connect(path)


def _event(conn: sqlite3.Connection, kind: str, at: str, stage: str | None = None) -> int:
    raw = events.RawEvent(lead_id=1, type=kind, at=at, stage=stage)
    return events.log_event(conn, events.validate_event(raw, NOW)).event_id


def _correct(conn: sqlite3.Connection, voids_id: int) -> int:
    raw = events.RawCorrection(lead_id=1, voids_id=voids_id, at="2026-11-16 12:00")
    return events.log_correction(conn, events.validate_correction(raw, NOW)).correction_id


def _time(conn: sqlite3.Connection, hours: str) -> int:
    raw = events.RawTime(hours=hours, date="2026-11-16", category="outreach")
    return events.log_time(conn, events.validate_time(raw, date(2026, 11, 30)))


def test_void_predicate_is_written_once_in_the_module() -> None:
    source = inspect.getsource(events)
    assert source.count("voids_activity_id = ") == 1
    assert source.count("c.type = 'correction'") == 1


def test_one_void_definition_agrees_with_counts_and_refusals(conn: sqlite3.Connection) -> None:
    try:
        kept_call = _event(conn, "call", "2026-11-16 09:00")
        voided_call = _event(conn, "call", "2026-11-16 09:30")
        moved = _event(conn, "call", "2026-11-16 10:00", stage="researched")
        kept_time = _time(conn, "1.5")
        voided_time = _time(conn, "2")

        call_fix = _correct(conn, voided_call)
        move_fix = _correct(conn, moved)
        time_fix = events.void_entry(conn, voided_time, events.TIME_KIND, "founder", NOW)

        voided = {voided_call: call_fix, moved: move_fix, voided_time: time_fix}
        for activity_id in (kept_call, kept_time):
            assert events._voided_by(conn, activity_id) is None
        for activity_id, fix_id in voided.items():
            assert events._voided_by(conn, activity_id) == fix_id

        # The SQL fragment and the helper are the same rule.
        fragment = events._voided_sql("a.id")
        rows = conn.execute(f"SELECT a.id, {fragment} AS v FROM activities a").fetchall()
        flagged = {int(r["id"]) for r in rows if r["v"]}
        assert flagged == set(voided)

        # Counting drops exactly what the rule calls void (plus corrections and the voided
        # move's stage change and its revert).
        counted = {int(r["id"]) for r in events.counted_activities(conn)}
        assert counted.isdisjoint(flagged)
        assert {kept_call, kept_time} <= counted
        assert all(
            events._voided_by(conn, int(r["id"])) is None for r in events.counted_activities(conn)
        )

        # Both already-void refusals name the correction the helper finds.
        with pytest.raises(events.EventError, match=f"correction {call_fix}\\)"):
            _correct(conn, voided_call)
        with pytest.raises(events.EventError, match=f"correction {time_fix}\\)"):
            events.void_entry(conn, voided_time, events.TIME_KIND, "founder", NOW)
    finally:
        conn.close()
