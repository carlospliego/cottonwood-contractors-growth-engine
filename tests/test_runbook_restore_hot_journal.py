# sir-target: tests/test_runbook_restore_hot_journal.py
"""Following the restore steps after a crash mid-write leaves both databases intact (R-33)."""

from __future__ import annotations

import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cottonwood import backup, db
from cottonwood.cli import EXIT_OK, main

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = REPO_ROOT / "docs" / "runbook.md"
LIVE = Path("data") / "cottonwood.db"
SET_ASIDE = Path("data") / "cottonwood.db.before-restore-20261115T100000Z"
BACKUP_TIME = datetime(2026, 11, 14, 9, 0, 0, tzinfo=UTC)
SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")
COMMITTED_AFTER_BACKUP = 500

# Starts a large write with a one-page cache, so changed pages spill into the database file
# before commit, then dies without committing or rolling back: a hot journal is left behind.
CRASH_SCRIPT = """
import os, sqlite3, sys
conn = sqlite3.connect(sys.argv[1], isolation_level=None)
conn.execute("PRAGMA cache_size=1")
conn.execute("BEGIN")
for i in range(3000):
    conn.execute(
        "INSERT INTO suppression (email_norm, reason, source, added_at) VALUES (?, ?, ?, ?)",
        (f"crash{i}-" + "x" * 200 + "@example.com", "opt_out", "reply", "2026-11-15T09:45:00Z"),
    )
os._exit(0)
"""


def _restore_commands() -> list[str]:
    text = RUNBOOK.read_text(encoding="utf-8")
    match = re.search(r"^## Restore from backup\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, "runbook has no '## Restore from backup' section"
    # Each command sits on its own line as a single code span.
    return [str(cmd) for cmd in re.findall(r"^\s+`([^`]+)`\s*$", match.group(1), re.M)]


def _is_sidecar(path: str) -> bool:
    return path.endswith(SIDECAR_SUFFIXES)


def _run(command: str) -> None:
    """Carry out one documented command the way the founder would, from the data's parent."""
    args = shlex.split(command)
    if args == ["uv", "run", "cottonwood", "backup"]:
        # Step 1 is only for a live database that still opens; this one is treated as damaged.
        return
    if args == ["uv", "run", "cottonwood", "migrate"]:
        assert main(["migrate", "--db", str(LIVE)]) == EXIT_OK
        return
    if args[0] == "mv" and len(args) == 3:
        if _is_sidecar(args[1]) and not Path(args[1]).exists():
            return  # "for each of these files that exists"
        shutil.move(args[1], args[2])
        return
    if args[0] == "cp" and len(args) == 3:
        shutil.copyfile(args[1], args[2])
        return
    if args[0] == "ls" and len(args) == 2:
        leftovers = sorted(Path().glob(args[1]))
        assert leftovers == [], f"files left under the live name: {leftovers}"
        return
    if args[0] == "sqlite3" and len(args) == 3:
        conn = sqlite3.connect(args[1])
        try:
            rows = conn.execute(args[2].rstrip(";")).fetchall()
        finally:
            conn.close()
        if "PRAGMA integrity_check" in args[2]:
            assert rows == [("ok",)], f"{command} printed {rows}"
        return
    pytest.fail(f"runbook command this test does not know how to run: {command}")


def test_restore_after_a_crash_mid_write_keeps_both_databases_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    backups = Path("data") / "backups"
    backups.mkdir(parents=True)

    db.migrate(LIVE)
    conn = db.connect(LIVE)
    try:
        conn.execute(
            "INSERT INTO suppression (email_norm, reason, source, added_at) VALUES (?, ?, ?, ?)",
            ("early@example.com", "opt_out", "reply", "2026-11-14T08:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()
    backup.backup(LIVE, backups, now=lambda: BACKUP_TIME)

    # Opt-outs committed after the backup, then a crash in the middle of the next write.
    conn = db.connect(LIVE)
    try:
        conn.executemany(
            "INSERT INTO suppression (email_norm, reason, source, added_at) VALUES (?, ?, ?, ?)",
            [
                (f"late{i}@example.com", "opt_out", "reply", "2026-11-15T09:30:00Z")
                for i in range(COMMITTED_AFTER_BACKUP)
            ],
        )
        conn.commit()
    finally:
        conn.close()
    subprocess.run([sys.executable, "-c", CRASH_SCRIPT, str(LIVE)], check=True)
    journal = Path(f"{LIVE}-journal")
    assert journal.is_file() and journal.stat().st_size > 0, "crash left no hot journal"

    commands = _restore_commands()
    assert commands, "restore section lists no commands"
    for command in commands:
        _run(command)

    # The restored database is the backup, intact, and can take the re-apply.
    conn = sqlite3.connect(LIVE)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT count(*) FROM suppression").fetchone()[0] == 1
    finally:
        conn.close()

    # The set-aside database still holds every committed opt-out, so they can be re-applied.
    conn = sqlite3.connect(SET_ASIDE)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        count = conn.execute("SELECT count(*) FROM suppression").fetchone()[0]
        assert count == 1 + COMMITTED_AFTER_BACKUP
    finally:
        conn.close()
