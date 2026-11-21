"""Runs the documented restore and suppression re-apply steps on scratch databases (R-33)."""

from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cottonwood import backup, db
from cottonwood.cli import EXIT_OK, main

LATEST_VERSION = len(db.discover_migrations())
REPO_ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = REPO_ROOT / "docs" / "runbook.md"
# The file names the runbook's example commands and SQL use.
SET_ASIDE = Path("data") / "cottonwood.db.before-restore-20261115T100000Z"
BACKUP_TIME = datetime(2026, 11, 14, 9, 0, 0, tzinfo=UTC)


def _section(title: str) -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, f"runbook has no '## {title}' section"
    return match.group(1)


def _reapply_sql() -> str:
    blocks = re.findall(
        r"```sql\n(.*?)```", _section("Re-applying suppression after a restore"), re.S
    )
    assert blocks, "re-apply section has no SQL block"
    return str(blocks[0])


def _suppress(path: Path, email: str, added_at: str) -> None:
    conn = db.connect(path)
    try:
        conn.execute(
            "INSERT INTO suppression (email_norm, reason, source, added_at) VALUES (?, ?, ?, ?)",
            (email, "opt_out", "reply", added_at),
        )
        conn.commit()
    finally:
        conn.close()


def _emails(conn: sqlite3.Connection) -> list[str]:
    return sorted(str(row[0]) for row in conn.execute("SELECT email_norm FROM suppression"))


def test_restore_section_lists_the_steps_in_order() -> None:
    section = _section("Restore from backup")
    steps = [
        "data/cottonwood.db.before-restore-",  # set the current database aside
        "cp data/backups/cottonwood-",  # copy the backup into place
        "PRAGMA integrity_check",
        "SELECT count(*) FROM suppression",
        "cottonwood migrate",
    ]
    positions = [section.find(step) for step in steps]
    assert -1 not in positions, dict(zip(steps, positions, strict=True))
    assert positions == sorted(positions)


def test_reapply_section_copies_newer_rows_from_the_set_aside_database() -> None:
    sql = _reapply_sql()
    assert "ATTACH DATABASE 'data/cottonwood.db.before-restore-" in sql
    assert "INSERT OR IGNORE INTO suppression" in sql
    assert "FROM before_restore.suppression" in sql
    assert "WHERE added_at >" in sql


def test_deletion_section_backs_up_clears_fields_and_keeps_suppression() -> None:
    section = _section("Deletion requests")
    backup_at = section.find("cottonwood backup")
    clear_at = section.find("UPDATE contacts")
    # find() returns -1 for a missing phrase, which would sort first; require both.
    assert backup_at != -1, "deletion section no longer says to run `cottonwood backup`"
    assert clear_at != -1, "deletion section no longer shows the UPDATE contacts step"
    assert backup_at < clear_at
    for field in ("name = NULL", "email = NULL", "email_norm = NULL", "phone_e164 = NULL"):
        assert field in section
    assert "deleted_at" in section
    assert "Keep the suppression entry" in section


def test_documented_restore_recovers_backup_and_newer_suppression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    backups = data / "backups"
    backups.mkdir(parents=True)
    live = data / "cottonwood.db"

    # A live database with one opt-out, backed up, then a second opt-out after the backup.
    db.migrate(live)
    _suppress(live, "early@example.com", "2026-11-14T08:00:00Z")
    snapshot = backup.backup(live, backups, now=lambda: BACKUP_TIME)
    _suppress(live, "late@example.com", "2026-11-15T09:30:00Z")

    # Steps 2-3: set the current database aside, copy the backup into place.
    shutil.move(live, SET_ASIDE)
    shutil.copyfile(snapshot, live)

    # Steps 4-5: integrity_check is ok and the suppression table is there.
    conn = sqlite3.connect(live)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT count(*) FROM suppression").fetchone()[0] == 1
    finally:
        conn.close()

    # Step 6: cottonwood migrate on the restored file.
    assert main(["migrate", "--db", str(live)]) == EXIT_OK
    assert f"at version {LATEST_VERSION}" in capsys.readouterr().out

    # Step 7: the runbook's own re-apply SQL, run against the restored database.
    conn = db.connect(live)
    try:
        conn.executescript(_reapply_sql())
        assert _emails(conn) == ["early@example.com", "late@example.com"]
        # Running it again is harmless.
        conn.executescript(_reapply_sql())
        assert _emails(conn) == ["early@example.com", "late@example.com"]
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()
    assert SET_ASIDE.is_file()
