# sir-target: tests/test_db_error_base.py
"""db.connect raises a general DatabaseError; MigrationError is one kind (F-maintainability-3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db


def test_migration_error_is_a_database_error() -> None:
    assert issubclass(db.MigrationError, db.DatabaseError)


def test_connect_on_a_missing_file_raises_a_database_error(tmp_path: Path) -> None:
    with pytest.raises(db.DatabaseError):
        db.connect(tmp_path / "missing.db")


def test_connect_open_failure_is_a_database_error_not_a_migration_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "present.db"
    path.write_bytes(b"")

    def refuse(*_args: object, **_kwargs: object) -> sqlite3.Connection:
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(sqlite3, "connect", refuse)
    with pytest.raises(db.DatabaseError, match="cannot open database") as caught:
        db.connect(path)
    assert not isinstance(caught.value, db.MigrationError)
