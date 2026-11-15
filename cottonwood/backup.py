"""Consistent database backups with the SQLite backup API (R-34)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from cottonwood.db import BUSY_TIMEOUT_SECONDS


class BackupError(Exception):
    """A backup could not be written."""


class BackupFolderMissingError(BackupError):
    """The folder the backup should go into does not exist."""

    def __init__(self, folder: Path) -> None:
        super().__init__(f"backup folder does not exist: {folder}")
        self.folder = folder


class DatabaseMissingError(BackupError):
    """The database to back up does not exist."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"database does not exist: {path}")
        self.path = path


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _claim_name(dest_dir: Path, stamp: str) -> Path:
    """Create and return a new, unused file cottonwood-<stamp>[-N].db in ``dest_dir``.

    The file is created exclusively, so two backups in the same second never share a name.
    """
    suffix = 1
    while True:
        name = f"cottonwood-{stamp}.db" if suffix == 1 else f"cottonwood-{stamp}-{suffix}.db"
        candidate = dest_dir / name
        try:
            candidate.touch(exist_ok=False)
        except FileExistsError:
            suffix += 1
            continue
        return candidate


def backup(db_path: Path, dest_dir: Path, now: Callable[[], datetime] = _utc_now) -> Path:
    """Copy ``db_path`` into ``dest_dir`` as cottonwood-YYYYMMDDTHHMMSSZ.db; return the new path."""
    if not dest_dir.is_dir():
        raise BackupFolderMissingError(dest_dir)
    if not db_path.is_file():
        raise DatabaseMissingError(db_path)
    stamp = now().astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = _claim_name(dest_dir, stamp)
    try:
        # mode=ro: a backup must never create or change the source.
        source = sqlite3.connect(
            f"{db_path.resolve().as_uri()}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_SECONDS
        )
        try:
            copy = sqlite3.connect(target)
            try:
                source.backup(copy)
            finally:
                copy.close()
        finally:
            source.close()
    except sqlite3.Error as exc:
        target.unlink(missing_ok=True)
        raise BackupError(f"backup of {db_path} failed: {exc}") from exc
    return target
