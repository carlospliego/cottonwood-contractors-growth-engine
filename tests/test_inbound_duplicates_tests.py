# sir-target: tests/test_inbound_duplicates_tests.py
"""Test inquiries take part in the log-inbound same-day duplicate check (R-2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _log(db_path: Path, received: str, *args: str) -> int:
    return main(
        [
            "log-inbound",
            "--db",
            str(db_path),
            "--channel",
            "form",
            "--segment",
            "commercial",
            "--received",
            received,
            *args,
        ]
    )


def _leads(db_path: Path) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute("SELECT id, is_test FROM leads ORDER BY id"))
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("first", "second"),
    [(("--test",), ()), ((), ("--test",)), (("--test",), ("--test",))],
    ids=["test-then-real", "real-then-test", "test-then-test"],
)
def test_test_inquiries_take_part_in_duplicate_check(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> None:
    assert _log(db_path, "2026-11-16 09:30", "--email", "pat@example.com", *first) == EXIT_OK
    capsys.readouterr()
    leads = _leads(db_path)
    assert [int(r[1]) for r in leads] == [1 if first else 0]
    code = _log(db_path, "2026-11-16 15:00", "--email", "PAT@example.com", *second)
    assert code == EXIT_REFUSED
    assert f"warning: possible duplicate of lead(s) {int(leads[0][0])}" in capsys.readouterr().err
    assert len(_leads(db_path)) == 1
