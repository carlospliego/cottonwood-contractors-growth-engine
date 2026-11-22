# sir-target: tests/test_apply_error_branches.py
"""_apply's unreadable-file and rollback branches, and --version (F-testing-2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main


def _migrate_from(monkeypatch: pytest.MonkeyPatch, migrations: Path) -> None:
    """Make `cottonwood migrate` read its migrations from ``migrations``."""
    real_migrate = db.migrate

    def migrate(db_path: Path) -> db.MigrateResult:
        return real_migrate(db_path, migrations)

    monkeypatch.setattr(db, "migrate", migrate)


def test_a_non_utf8_migration_is_an_error_line_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_latin1.sql").write_bytes(b"-- caf\xe9\nCREATE TABLE t (id INTEGER);\n")
    _migrate_from(monkeypatch, migrations)

    assert main(["migrate", "--db", str(tmp_path / "x.db")]) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "001_latin1.sql" in err
    assert "Traceback" not in err


def test_no_transaction_is_left_open_after_a_failed_migration(tmp_path: Path) -> None:
    (tmp_path / "001_bad.sql").write_text("CREATE TABLE ok (id INTEGER);\nNOT SQL;\n")
    [migration] = db.discover_migrations(tmp_path)
    conn = sqlite3.connect(tmp_path / "x.db", autocommit=True)
    try:
        with pytest.raises(db.MigrationError, match="001_bad.sql"):
            db._apply(conn, migration)
        assert conn.in_transaction is False
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        assert tables == []
    finally:
        conn.close()


def test_version_prints_the_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == EXIT_OK
    assert capsys.readouterr().out == "cottonwood 0.1.0\n"
