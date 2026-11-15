# sir-target: tests/test_migrate_concurrency.py
"""Regression test: a run that read a stale user_version must not re-apply a migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db


def test_migration_applied_by_another_run_after_version_read_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_log.sql").write_text(
        "CREATE TABLE IF NOT EXISTS log (s TEXT);\nINSERT INTO log VALUES ('x');\n"
    )
    path = tmp_path / "race.db"
    original = db._read_version
    calls = 0

    def stale_read(conn: sqlite3.Connection, db_path: Path) -> int:
        # The first read returns the version seen before another run applies 001.
        nonlocal calls
        calls += 1
        version = original(conn, db_path)
        if calls == 1:
            other = sqlite3.connect(path, isolation_level=None)
            try:
                other.executescript(
                    "BEGIN;\n"
                    "CREATE TABLE IF NOT EXISTS log (s TEXT);\n"
                    "INSERT INTO log VALUES ('x');\n"
                    "PRAGMA user_version = 1;\n"
                    "COMMIT;\n"
                )
            finally:
                other.close()
        return version

    monkeypatch.setattr(db, "_read_version", stale_read)

    result = db.migrate(path, migrations)

    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT COUNT(*) FROM log").fetchone()[0]
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()
    assert rows == 1
    assert version == 1
    assert result.applied == ()
    assert (result.from_version, result.to_version) == (0, 1)
