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


class DatabaseError(Exception):
    """The database could not be opened or used; base of every db error."""


class MigrationError(DatabaseError):
    """A migration could not be found, read or applied."""


class FolderMissingError(MigrationError):
    """The folder that should hold the database file does not exist."""

    def __init__(self, folder: Path) -> None:
        super().__init__(f"folder does not exist: {folder}")
        self.folder = folder


class DatabaseMissingError(MigrationError):
    """The database file does not exist (run `cottonwood migrate` first)."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"database does not exist: {path} (run `cottonwood migrate` first)")
        self.path = path


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


def connect(db_path: Path) -> sqlite3.Connection:
    """Open an existing database with foreign keys on, a busy timeout and sqlite3.Row rows.

    Unlike sqlite3.connect, a missing file is an error rather than a new empty database.
    """
    if not db_path.is_file():
        raise DatabaseMissingError(db_path)
    try:
        conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_SECONDS)
    except sqlite3.Error as exc:
        raise DatabaseError(f"cannot open database {db_path}: {exc}") from exc
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error as exc:
        conn.close()
        raise DatabaseError(f"cannot open database {db_path}: {exc}") from exc
    conn.row_factory = sqlite3.Row
    return conn


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


def require_migrated(
    conn: sqlite3.Connection, db_path: Path, migrations_dir: Path = MIGRATIONS_DIR
) -> None:
    """Refuse a database older than the newest migration, before a command reads or writes it."""
    migrations = discover_migrations(migrations_dir)
    newest = migrations[-1].number if migrations else 0
    current = _read_version(conn, db_path)
    if current < newest:
        raise MigrationError(
            f"database at version {current}, run `cottonwood migrate` "
            f"(needs version {newest}): {db_path}"
        )


def _read_version(conn: sqlite3.Connection, db_path: Path) -> int:
    """Return user_version, turning a SQLite error into a MigrationError naming ``db_path``."""
    try:
        return user_version(conn)
    except sqlite3.Error as exc:
        raise MigrationError(f"cannot read database {db_path}: {exc}") from exc


_TRANSACTION_KEYWORDS = frozenset({"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"})
_FIRST_WORD = re.compile(r"[A-Za-z]+")


def _statements(sql: str) -> list[str]:
    """Split ``sql`` into complete statements.

    sqlite3.complete_statement knows strings, comments and CREATE TRIGGER ... BEGIN ... END
    bodies, so a ';' inside any of them does not end a statement.
    """
    statements: list[str] = []
    pending = ""
    for piece in sql.split(";"):
        pending += piece + ";"
        if sqlite3.complete_statement(pending):
            statements.append(pending)
            pending = ""
    if pending.strip(" \t\r\n;"):
        statements.append(pending)
    return statements


def _first_keyword(statement: str) -> str:
    """Return a statement's first word in upper case, after leading comments."""
    text = statement.lstrip()
    while text.startswith(("--", "/*")):
        if text.startswith("--"):
            end = text.find("\n")
            text = "" if end == -1 else text[end + 1 :]
        else:
            end = text.find("*/")
            text = "" if end == -1 else text[end + 2 :]
        text = text.lstrip()
    match = _FIRST_WORD.match(text)
    return match.group(0).upper() if match else ""


def _transaction_control(sql: str) -> str | None:
    """Return the first transaction-control keyword a statement in ``sql`` starts with."""
    for statement in _statements(sql):
        keyword = _first_keyword(statement)
        if keyword in _TRANSACTION_KEYWORDS:
            return keyword
    return None


def _apply(conn: sqlite3.Connection, migration: Migration) -> bool:
    """Run one migration and set user_version to its number, in one transaction.

    The write lock is taken first and user_version re-read under it, so a migration
    another run applied meanwhile is skipped; returns False in that case.

    Migration files must not contain BEGIN, COMMIT or ROLLBACK: the runner wraps each file
    in its own transaction. A file with its own transaction control is refused before it
    runs: a COMMIT inside it would commit part of the file and the version bump
    outside the runner's transaction, where a later error could not roll them back.
    """
    try:
        sql = migration.path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MigrationError(f"cannot read migration {migration.path}: {exc}") from exc
    keyword = _transaction_control(sql)
    if keyword is not None:
        raise MigrationError(
            f"migration {migration.path.name} failed: it contains {keyword}; "
            "the runner wraps each file in its own transaction"
        )
    script = f"{sql}\n;\nPRAGMA user_version = {migration.number};\nCOMMIT;\n"
    try:
        conn.execute("BEGIN IMMEDIATE")
        if user_version(conn) >= migration.number:
            conn.execute("ROLLBACK")
            return False
        conn.executescript(script)
        # The script's own COMMIT must have closed the transaction and set the version.
        if conn.in_transaction:
            conn.execute("ROLLBACK")
            raise MigrationError(
                f"migration {migration.path.name} failed: a transaction was still open after it ran"
            )
        found = user_version(conn)
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise MigrationError(f"migration {migration.path.name} failed: {exc}") from exc
    if found != migration.number:
        raise MigrationError(
            f"migration {migration.path.name} failed: user_version is {found} after it ran,"
            f" expected {migration.number}"
        )
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
