# sir-target: tests/test_migrations_folder.py
"""Coverage for F-testing-1: discovering migrations from the default and a missing folder."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db


def test_default_migrations_dir_yields_numbered_migrations_from_001() -> None:
    migrations = db.discover_migrations()
    assert migrations, f"no migrations found in {db.MIGRATIONS_DIR}"
    assert [m.number for m in migrations] == list(range(1, len(migrations) + 1))
    assert migrations[0].path.name == "001_baseline.sql"


def test_missing_migrations_folder_raises_migration_error_naming_it(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-migrations"

    with pytest.raises(db.MigrationError, match="migrations folder does not exist") as excinfo:
        db.discover_migrations(missing)

    assert str(missing) in str(excinfo.value)


def test_migrate_with_missing_migrations_folder_creates_no_database(tmp_path: Path) -> None:
    db_path = tmp_path / "cottonwood.db"

    with pytest.raises(db.MigrationError, match="migrations folder does not exist"):
        db.migrate(db_path, tmp_path / "no-such-migrations")

    assert not db_path.exists()
