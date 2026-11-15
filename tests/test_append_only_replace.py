# sir-target: tests/test_append_only_replace.py
"""INSERT OR REPLACE must not overwrite suppression or activity rows (R-17, R-24)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from cottonwood import db

NOW = "2026-11-15T10:00:00Z"
LATER = "2027-01-01T00:00:00Z"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    path = tmp_path / "replace.db"
    db.migrate(path)
    connection = db.connect(path)
    try:
        yield connection
    finally:
        connection.close()


def _suppression_rows(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return [tuple(row) for row in conn.execute("SELECT * FROM suppression")]


def _activity(conn: sqlite3.Connection, activity_id: int) -> tuple[object, ...]:
    row = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    return tuple(row)


def test_insert_or_replace_keeps_the_existing_suppression_entry(
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        "INSERT INTO suppression (email_norm, reason, source, added_at)"
        " VALUES ('jane@example.com', 'opt_out', 'reply', ?)",
        (NOW,),
    )
    conn.commit()

    conn.execute(
        "INSERT OR REPLACE INTO suppression (email_norm, reason, source, added_at)"
        " VALUES ('jane@example.com', 'changed', 'someone', ?)",
        (LATER,),
    )
    conn.commit()

    assert _suppression_rows(conn) == [("jane@example.com", "opt_out", "reply", NOW)]


def test_insert_or_ignore_still_skips_an_existing_suppression_entry(
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        "INSERT INTO suppression (email_norm, reason, source, added_at)"
        " VALUES ('jane@example.com', 'opt_out', 'reply', ?)",
        (NOW,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO suppression (email_norm, reason, source, added_at)"
        " VALUES ('jane@example.com', 'deletion_request', 'founder', ?)",
        (LATER,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO suppression (email_norm, reason, source, added_at)"
        " VALUES ('new@example.com', 'opt_out', 'reply', ?)",
        (LATER,),
    )
    conn.commit()

    assert sorted(_suppression_rows(conn), key=str) == [
        ("jane@example.com", "opt_out", "reply", NOW),
        ("new@example.com", "opt_out", "reply", LATER),
    ]


def test_insert_or_replace_of_an_activity_is_rejected_and_row_unchanged(
    conn: sqlite3.Connection,
) -> None:
    cur = conn.execute(
        "INSERT INTO activities (type, payload, actor, occurred_at, recorded_at)"
        " VALUES ('inquiry_logged', '{\"note\": \"first\"}', 'founder', ?, ?)",
        (NOW, NOW),
    )
    conn.commit()
    assert cur.lastrowid is not None
    activity_id = cur.lastrowid
    before = _activity(conn, activity_id)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(
            "INSERT OR REPLACE INTO activities"
            " (id, type, payload, actor, occurred_at, recorded_at)"
            " VALUES (?, 'note', '{}', 'someone', ?, ?)",
            (activity_id, LATER, LATER),
        )
    conn.rollback()

    assert _activity(conn, activity_id) == before
