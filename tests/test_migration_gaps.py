# sir-target: tests/test_migration_gaps.py
"""Regression test for F-correctness-7: gaps in migration numbers must be rejected."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db


def _version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def test_gap_in_migration_numbers_is_rejected_and_names_the_missing_number(
    tmp_path: Path,
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_create.sql").write_text("CREATE TABLE a (id INTEGER);\n")
    (migrations / "003_later.sql").write_text("CREATE TABLE c (id INTEGER);\n")

    with pytest.raises(db.MigrationError, match="002"):
        db.discover_migrations(migrations)


def test_migrate_with_gap_applies_nothing(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_create.sql").write_text("CREATE TABLE a (id INTEGER);\n")
    (migrations / "003_later.sql").write_text("CREATE TABLE c (id INTEGER);\n")
    path = tmp_path / "x.db"

    with pytest.raises(db.MigrationError, match="002"):
        db.migrate(path, migrations)

    assert not path.exists() or _version(path) == 0


def test_contiguous_and_empty_migration_folders_are_accepted(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert db.discover_migrations(empty) == []

    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "002_b.sql").write_text("SELECT 1;\n")
    (migrations / "001_a.sql").write_text("SELECT 1;\n")
    assert [m.number for m in db.discover_migrations(migrations)] == [1, 2]
