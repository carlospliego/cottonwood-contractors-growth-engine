# sir-target: tests/test_rowid_single_helper.py
"""Every insert's row id goes through _shared._rowid (CCGE-155).

deletion, eligibility and send kept their own copy of the "no row id" check, and record_run
returned int(cursor.lastrowid or 0), so a missing id was reported as run 0.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

import cottonwood
from cottonwood import _shared, db, deletion, eligibility, runs, send

PACKAGE = Path(cottonwood.__file__).resolve().parent


class _NoIdCursor:
    lastrowid = None


class _NoIdOnRunInsert:
    """A real connection whose agent_runs INSERT reports no row id."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: Any = ()) -> Any:
        cursor = self._conn.execute(sql, params)
        if sql.startswith("INSERT INTO agent_runs"):
            return _NoIdCursor()
        return cursor

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


def _record() -> runs.RunRecord:
    return runs.build_record(
        skill="research-prospects",
        skill_version="1.0.0",
        model="claude-opus-5-5",
        started="2026-11-30 09:00",
        ended="2026-11-30 09:40",
        input_ref="brief",
        output_ref="out/research/x.json",
        validation="passed",
        tokens="1200",
        cost=None,
        cost_source=None,
        estimated=False,
        now="2026-12-01T00:00:00Z",
    )


def test_lastrowid_appears_only_in_shared() -> None:
    found = sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "lastrowid" in path.read_text(encoding="utf-8")
    )
    assert found == ["_shared.py"]


def test_the_modules_bind_the_shared_helper() -> None:
    for module in (deletion, eligibility, send, runs):
        assert vars(module)["_rowid"] is _shared._rowid


def test_record_run_raises_when_the_insert_has_no_row_id(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        wrapper = cast(sqlite3.Connection, _NoIdOnRunInsert(conn))
        with pytest.raises(sqlite3.DatabaseError, match="no row id"):
            runs.record_run(wrapper, _record())
        # The run is rolled back, not left behind without an id.
        assert conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0] == 0
    finally:
        conn.close()


def test_record_run_still_returns_the_new_id(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        assert runs.record_run(conn, _record()) == 1
        assert runs.record_run(conn, _record()) == 2
    finally:
        conn.close()
