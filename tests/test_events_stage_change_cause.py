# sir-target: tests/test_events_stage_change_cause.py
"""A stage_change's cause key names an R-15 event or, for a revert, a correction (AC-4.3)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
T1 = "2026-11-16 09:30"
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


def _cause_type(conn: sqlite3.Connection, stage_change: sqlite3.Row) -> str:
    cause_id = json.loads(stage_change["payload"])[events.STAGE_CHANGE_CAUSE_KEY]
    row = conn.execute("SELECT type FROM activities WHERE id = ?", (cause_id,)).fetchone()
    return str(row[0])


def test_cause_key_is_the_documented_payload_key() -> None:
    assert events.STAGE_CHANGE_CAUSE_KEY == "event_activity_id"


def test_revert_and_event_moves_are_told_apart_by_their_cause(db_path: Path) -> None:
    assert _event(db_path, "1", "walkthrough", "--at", T1, "--stage", "walkthrough") == EXIT_OK
    conn = db.connect(db_path)
    try:
        walk = conn.execute("SELECT id FROM activities WHERE type = 'walkthrough'").fetchone()
        walk_id = int(walk[0])
    finally:
        conn.close()
    assert _event(db_path, "1", "correction", "--voids", str(walk_id), "--at", T_FIX) == EXIT_OK

    conn = db.connect(db_path)
    try:
        changes = list(
            conn.execute(
                "SELECT id, payload FROM activities WHERE type = 'stage_change' ORDER BY id"
            )
        )
        assert len(changes) == 2
        move, revert = changes
        assert _cause_type(conn, move) == "walkthrough"
        assert _cause_type(conn, move) in events.EVENT_TYPES
        assert _cause_type(conn, revert) == "correction"
        assert events.is_revert(conn, int(move["id"])) is False
        assert events.is_revert(conn, int(revert["id"])) is True
        assert events.is_revert(conn, walk_id) is False
    finally:
        conn.close()
