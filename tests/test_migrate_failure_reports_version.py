# sir-target: tests/test_migrate_failure_reports_version.py
"""A failed migration says which version the database is now at (F-correctness-8)."""

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


def test_a_failure_after_a_committed_migration_names_the_file_and_the_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_ok.sql").write_text("CREATE TABLE ok (id INTEGER);\n", encoding="utf-8")
    (migrations / "002_bad.sql").write_text("CREATE TABLE (;\n", encoding="utf-8")
    path = tmp_path / "new.db"
    _migrate_from(monkeypatch, migrations)

    assert main(["migrate", "--db", str(path)]) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "002_bad.sql" in err
    assert "version 1" in err
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        conn.close()
