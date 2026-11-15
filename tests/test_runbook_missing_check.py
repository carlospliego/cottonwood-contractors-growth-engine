# sir-target: tests/test_runbook_missing_check.py
"""The runbook's 'missing' check counts set-aside entries absent from the restored DB (R-24)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = REPO_ROOT / "docs" / "runbook.md"
# A plain table with no NOT NULL, as in a hand-edited restored or set-aside file.
LOOSE_SCHEMA = (
    "CREATE TABLE suppression (email_norm TEXT PRIMARY KEY, reason TEXT, source TEXT, "
    "added_at TEXT);"
)


def _missing_query() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    section = re.search(
        r"^## Re-applying suppression after a restore\n(.*?)(?=^## |\Z)", text, re.M | re.S
    )
    assert section is not None, "runbook has no re-apply section"
    blocks = re.findall(r"```sql\n(.*?)```", section.group(1), re.S)
    assert blocks, "re-apply section has no SQL block"
    query = re.search(r"SELECT count\(\*\) AS missing.*?;", str(blocks[0]), re.S)
    assert query is not None, "re-apply SQL has no 'missing' check"
    return query.group(0)


def _make_db(path: Path, emails: list[str | None]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(LOOSE_SCHEMA)
        conn.executemany(
            "INSERT INTO suppression (email_norm, reason, source, added_at) "
            "VALUES (?, 'opt_out', 'reply', '2026-11-14T08:00:00Z')",
            [(email,) for email in emails],
        )
        conn.commit()
    finally:
        conn.close()


def _missing(tmp_path: Path, restored: list[str | None], set_aside: list[str | None]) -> int:
    main_path = tmp_path / "restored.db"
    aside_path = tmp_path / "set-aside.db"
    _make_db(main_path, restored)
    _make_db(aside_path, set_aside)
    conn = sqlite3.connect(main_path)
    try:
        conn.execute("ATTACH DATABASE ? AS before_restore", (str(aside_path),))
        row = conn.execute(_missing_query()).fetchone()
        return int(row[0])
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("restored", "set_aside", "expected"),
    [
        # A NULL key in the restored table must not hide a missing address.
        ([None], ["early@example.com"], 1),
        ([None, "late@example.com"], ["early@example.com", "late@example.com"], 1),
        # A NULL or empty key on the set-aside side counts as missing.
        (["early@example.com"], ["early@example.com", None], 1),
        (["early@example.com", ""], ["early@example.com", ""], 1),
        # Everything present: nothing missing.
        (["early@example.com", "late@example.com"], ["early@example.com"], 0),
    ],
)
def test_missing_check_counts_absent_entries(
    tmp_path: Path, restored: list[str | None], set_aside: list[str | None], expected: int
) -> None:
    assert _missing(tmp_path, restored, set_aside) == expected
