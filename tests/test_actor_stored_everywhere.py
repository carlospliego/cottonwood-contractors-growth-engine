# sir-target: tests/test_actor_stored_everywhere.py
"""--actor reaches every row entries, voids and a correction write (F-testing-4)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
ACTOR = "founder"  # not the default actor (developer), so a dropped --actor shows


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _run(db_path: Path, *args: str) -> None:
    command, *rest = args
    assert main([command, "--db", str(db_path), *rest, "--actor", ACTOR]) == EXIT_OK


def _rows(db_path: Path) -> list[tuple[int, str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        return [
            (int(r[0]), str(r[1]), str(r[2]))
            for r in conn.execute("SELECT id, type, actor FROM activities ORDER BY id")
        ]
    finally:
        conn.close()


def test_entries_and_their_voids_store_the_actor(db_path: Path) -> None:
    _run(db_path, "log-time", "1.5", "--date", "2026-11-16", "--category", "calls")
    _run(db_path, "log-cost", "49.00", "--date", "2026-11-16", "--category", "tools")
    _run(db_path, "log-time", "--voids", "1")
    _run(db_path, "log-cost", "--voids", "2")

    rows = _rows(db_path)
    assert [kind for _, kind, _ in rows] == [
        "time_logged",
        "cost_logged",
        "correction",
        "correction",
    ]
    assert {actor for _, _, actor in rows} == {ACTOR}


def test_a_reverting_correction_and_its_stage_change_store_the_actor(db_path: Path) -> None:
    inbound = ["--channel", "phone", "--received", "2026-11-15 08:00", "--segment", "commercial"]
    _run(db_path, "log-inbound", *inbound, "--name", "Pat Lee")
    _run(db_path, "log-event", "1", "call", "--at", "2026-11-16 09:30", "--stage", "researched")
    before = {row_id for row_id, _, _ in _rows(db_path)}
    _run(db_path, "log-event", "1", "correction", "--voids", "2", "--at", "2026-11-16 10:00")

    written = [row for row in _rows(db_path) if row[0] not in before]
    assert sorted(kind for _, kind, _ in written) == ["correction", "stage_change"]
    assert {actor for _, _, actor in written} == {ACTOR}
    # Every row in the database, the original event and its move included.
    assert {actor for _, _, actor in _rows(db_path)} == {ACTOR}
