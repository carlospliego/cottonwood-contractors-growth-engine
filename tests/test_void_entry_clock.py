# sir-target: tests/test_void_entry_clock.py
"""void_entry reads the current time itself, like the other log functions (F-maintainability-5)."""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


def test_void_entry_takes_no_time_argument() -> None:
    assert "now" not in inspect.signature(events.void_entry).parameters


def test_the_correction_is_stamped_with_the_clock(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        entry = events.TimeEntry(
            hours=Decimal("1.5"),
            date=date(2026, 11, 16),
            category="outreach",
            person="founder",
            estimated=False,
            note=None,
            actor="developer",
        )
        time_id = events.log_time(conn, entry)
        fix_id = events.void_entry(conn, time_id, events.TIME_KIND, "founder", "wrong day")
        row = conn.execute(
            "SELECT occurred_at, recorded_at, voids_activity_id FROM activities WHERE id = ?",
            (fix_id,),
        ).fetchone()
    finally:
        conn.close()
    assert (row["occurred_at"], row["recorded_at"]) == (NOW, NOW)
    assert row["voids_activity_id"] == time_id


def test_a_blank_actor_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        with pytest.raises(events.EventError, match="actor"):
            events.void_entry(conn, 1, events.TIME_KIND, "   ")
    finally:
        conn.close()
