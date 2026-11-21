# sir-target: tests/test_unmigrated_db_refused.py
"""log-inbound and review refuse a database older than the newest migration (F-correctness-6)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_REFUSED, main

LOG_ARGS = (
    "--channel",
    "form",
    "--received",
    "2026-11-16 09:30",
    "--segment",
    "commercial",
    "--name",
    "Pat Lee",
    "--email",
    "pat@example.com",
)
NEWEST = db.discover_migrations()[-1].number


def _at_version(path: Path, version: int) -> None:
    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA user_version = {version}")
    raw.close()


@pytest.mark.parametrize("version", [0, 1, NEWEST - 1])
@pytest.mark.parametrize("command", ["log-inbound", "review"])
def test_an_old_database_is_refused_with_a_migrate_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, version: int
) -> None:
    path = tmp_path / "old.db"
    _at_version(path, version)
    args = [command, "--db", str(path)]
    if command == "log-inbound":
        args += list(LOG_ARGS)

    assert main(args) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert f"database at version {version}, run `cottonwood migrate`" in err
    assert "no such table" not in err


def test_require_migrated_accepts_a_current_database(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        db.require_migrated(conn, path)
    finally:
        conn.close()
