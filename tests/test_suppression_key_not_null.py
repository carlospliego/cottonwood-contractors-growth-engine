# sir-target: tests/test_suppression_key_not_null.py
"""suppression.email_norm must be a real address key: no NULL, no empty string (R-24)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from cottonwood import db

NOW = "2026-11-15T10:00:00Z"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    path = tmp_path / "suppression-key.db"
    db.migrate(path)
    connection = db.connect(path)
    try:
        yield connection
    finally:
        connection.close()


def _count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM suppression").fetchone()[0])


@pytest.mark.parametrize("key", [None, ""])
def test_suppression_rejects_a_null_or_empty_email_norm(
    conn: sqlite3.Connection, key: str | None
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO suppression (email_norm, reason, source, added_at)"
            " VALUES (?, 'opt_out', 'reply', ?)",
            (key, NOW),
        )
    conn.rollback()

    assert _count(conn) == 0


def test_suppression_rejects_a_second_null_email_norm(conn: sqlite3.Connection) -> None:
    for _ in range(2):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO suppression (email_norm, reason, source, added_at)"
                " VALUES (NULL, 'opt_out', 'reply', ?)",
                (NOW,),
            )
        conn.rollback()

    assert _count(conn) == 0


def test_suppression_still_accepts_a_real_address(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO suppression (email_norm, reason, source, added_at)"
        " VALUES ('jane@example.com', 'opt_out', 'reply', ?)",
        (NOW,),
    )
    conn.commit()

    assert _count(conn) == 1
