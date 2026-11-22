# sir-target: tests/test_migrate_newer_database.py
"""migrate refuses a database newer than the known migrations (F-correctness-3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_REFUSED, main


def _migrate_from(monkeypatch: pytest.MonkeyPatch, migrations: Path) -> None:
    """Make `cottonwood migrate` read its migrations from ``migrations``."""
    real_migrate = db.migrate

    def migrate(db_path: Path) -> db.MigrateResult:
        return real_migrate(db_path, migrations)

    monkeypatch.setattr(db, "migrate", migrate)


def test_a_database_at_version_5_with_only_001_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_only.sql").write_text("CREATE TABLE t (id INTEGER);\n", encoding="utf-8")
    path = tmp_path / "future.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA user_version = 5")
    finally:
        conn.close()
    _migrate_from(monkeypatch, migrations)

    assert main(["migrate", "--db", str(path)]) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "version 5" in err
    assert "migration 001" in err
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []
    finally:
        conn.close()
