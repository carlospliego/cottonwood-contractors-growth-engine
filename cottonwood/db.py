"""SQLite connection helpers and the migrations runner (PRAGMA user_version)."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

# Shipped inside the package so a regular (non-editable) wheel install finds them.
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DEFAULT_DB_PATH = Path("data") / "cottonwood.db"
DB_ENV_VAR = "COTTONWOOD_DB"
# Seconds a run waits for another run's write lock before giving up.
BUSY_TIMEOUT_SECONDS = 30.0

_MIGRATION_NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


class MigrationError(Exception):
    """A migration could not be found, read or applied."""


class FolderMissingError(MigrationError):
    """The folder that should hold the database file does not exist."""

    def __init__(self, folder: Path) -> None:
        super().__init__(f"folder does not exist: {folder}")
        self.folder = folder


@dataclass(frozen=True)
class Migration:
    """One migration file: its number and path."""

    number: int
    path: Path


@dataclass(frozen=True)
class MigrateResult:
    """The database's version before and after, and the migrations applied."""

    from_version: int
    to_version: int
    applied: tuple[Migration, ...]


def default_db_path() -> Path:
    """Return the database path: $COTTONWOOD_DB when set, else data/cottonwood.db."""
    value = os.environ.get(DB_ENV_VAR)
    return Path(value) if value else DEFAULT_DB_PATH


def discover_migrations(migrations_dir: Path = MIGRATIONS_DIR) -> list[Migration]:
    """List the NNN_<name>.sql files in ``migrations_dir`` in numeric order."""
    if not migrations_dir.is_dir():
        raise MigrationError(f"migrations folder does not exist: {migrations_dir}")
    found: dict[int, Migration] = {}
    for path in sorted(migrations_dir.glob("*.sql")):
        match = _MIGRATION_NAME.match(path.name)
        if match is None:
            raise MigrationError(f"migration file name is not NNN_<name>.sql: {path}")
        number = int(match.group(1))
        if number in found:
            raise MigrationError(
                f"two migrations share number {number:03d}: {found[number].path.name}, {path.name}"
            )
        found[number] = Migration(number, path)
    # user_version is a high-water mark, so a gap would let a later-added lower number be skipped.
    for expected, number in enumerate(sorted(found), start=1):
        if number != expected:
            raise MigrationError(
                f"migration numbers must run 001..NNN without gaps: {expected:03d} is missing"
                f" (found {found[number].path.name})"
            )
    return [found[number] for number in sorted(found)]


def user_version(conn: sqlite3.Connection) -> int:
    """Return the database's PRAGMA user_version."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _read_version(conn: sqlite3.Connection, db_path: Path) -> int:
    """Return user_version, turning a SQLite error into a MigrationError naming ``db_path``."""
    try:
        return user_version(conn)
    except sqlite3.Error as exc:
        raise MigrationError(f"cannot read database {db_path}: {exc}") from exc


def _apply(conn: sqlite3.Connection, migration: Migration) -> bool:
    """Run one migration and set user_version to its number, in one transaction.

    The write lock is taken first and user_version re-read under it, so a migration
    another run applied meanwhile is skipped; returns False in that case.
    """
    try:
        sql = migration.path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MigrationError(f"cannot read migration {migration.path}: {exc}") from exc
    script = f"{sql}\n;\nPRAGMA user_version = {migration.number};\nCOMMIT;\n"
    try:
        conn.execute("BEGIN IMMEDIATE")
        if user_version(conn) >= migration.number:
            conn.execute("ROLLBACK")
            return False
        conn.executescript(script)
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise MigrationError(f"migration {migration.path.name} failed: {exc}") from exc
    return True


def migrate(db_path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> MigrateResult:
    """Create or upgrade the database at ``db_path`` to the newest migration."""
    folder = db_path.parent
    if not folder.is_dir():
        raise FolderMissingError(folder)
    migrations = discover_migrations(migrations_dir)
    try:
        # autocommit=True: executescript must not commit the BEGIN IMMEDIATE that _apply opens.
        conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_SECONDS, autocommit=True)
    except sqlite3.Error as exc:
        raise MigrationError(f"cannot open database {db_path}: {exc}") from exc
    try:
        start = _read_version(conn, db_path)
        applied: list[Migration] = []
        for migration in migrations:
            if migration.number <= start:
                continue
            if _apply(conn, migration):
                applied.append(migration)
        return MigrateResult(start, _read_version(conn, db_path), tuple(applied))
    finally:
        conn.close()
