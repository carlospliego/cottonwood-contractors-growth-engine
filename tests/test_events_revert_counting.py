# sir-target: tests/test_events_revert_counting.py
"""A correction's stage revert is not a counted stage change (R-17, R-16, R-28)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
T1 = "2026-11-16 09:30"
T2 = "2026-11-16 09:45"
T_FIX = "2026-11-16 10:00"


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
            "--email",
            "pat@example.com",
        ]
    )
    assert code == EXIT_OK
    return path


def _event(db_path: Path, *args: str) -> int:
    return main(["log-event", "--db", str(db_path), *args])


def _last_id(db_path: Path, activity_type: str) -> int:
    conn = db.connect(db_path)
    try:
        row = conn.execute(
            "SELECT max(id) FROM activities WHERE type = ?", (activity_type,)
        ).fetchone()
        return int(row[0])
    finally:
        conn.close()


def test_revert_into_buyer_need_confirmed_is_not_a_counted_entry(db_path: Path) -> None:
    assert (
        _event(
            db_path,
            "1",
            "remote_screen",
            "--at",
            T1,
            "--stage",
            "buyer_need_confirmed",
            "--need",
            "roof",
        )
        == EXIT_OK
    )
    qualify_change = _last_id(db_path, "stage_change")
    assert _event(db_path, "1", "walkthrough", "--at", T2, "--stage", "walkthrough") == EXIT_OK
    walk_id = _last_id(db_path, "walkthrough")
    assert _event(db_path, "1", "correction", "--voids", str(walk_id), "--at", T_FIX) == EXIT_OK
    revert_id = _last_id(db_path, "stage_change")
    assert revert_id != qualify_change
    conn = db.connect(db_path)
    try:
        counted = events.counted_activities(conn, "stage_change")
        stage = str(conn.execute("SELECT stage FROM leads WHERE id = 1").fetchone()[0])
    finally:
        conn.close()
    assert stage == "buyer_need_confirmed"
    ids = [int(r["id"]) for r in counted]
    assert revert_id not in ids
    assert ids == [qualify_change]
    entries = [r for r in counted if json.loads(r["payload"])["to"] == "buyer_need_confirmed"]
    assert len(entries) == 1
