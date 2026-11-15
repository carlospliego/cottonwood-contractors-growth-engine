# sir-target: tests/test_inbound_review_errors.py
"""Tests for log-inbound and review error paths: rollback, sqlite3.Error, OSError (R-1, R-31)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, inbound
from cottonwood.cli import EXIT_REFUSED, main

TABLES = ("organizations", "contacts", "leads", "activities")

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
    "--company",
    "Acme Builders",
)

FAIL_ACTIVITY_TRIGGER = (
    "CREATE TRIGGER fail_activity BEFORE INSERT ON activities"
    " BEGIN SELECT RAISE(ABORT, 'forced activity failure'); END"
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: int(conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]) for t in TABLES}


def _make_version_1(path: Path) -> None:
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 1")
    raw.close()


def _add_failing_trigger(db_path: Path) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(FAIL_ACTIVITY_TRIGGER)
        conn.commit()
    finally:
        conn.close()


def _inquiry() -> inbound.Inquiry:
    return inbound.validate(
        inbound.RawInquiry(
            channel="form",
            received="2026-11-16 09:30",
            segment="commercial",
            name="Pat Lee",
            email="pat@example.com",
            company="Acme Builders",
        )
    )


def test_failed_activity_insert_rolls_back_every_row(db_path: Path) -> None:
    _add_failing_trigger(db_path)
    conn = db.connect(db_path)
    try:
        with pytest.raises(sqlite3.Error, match="forced activity failure"):
            inbound.log_inquiry(conn, _inquiry())
        # Same connection: without the rollback the earlier inserts would still be visible.
        assert not conn.in_transaction
        assert _counts(conn) == dict.fromkeys(TABLES, 0)
    finally:
        conn.close()
    conn = db.connect(db_path)
    try:
        assert _counts(conn) == dict.fromkeys(TABLES, 0)
    finally:
        conn.close()


def test_log_inbound_failed_insert_exits_1_and_saves_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _add_failing_trigger(db_path)

    code = main(["log-inbound", "--db", str(db_path), *LOG_ARGS])

    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    assert "error: could not save the inquiry" in err
    assert "Traceback" not in err
    conn = db.connect(db_path)
    try:
        assert _counts(conn) == dict.fromkeys(TABLES, 0)
    finally:
        conn.close()


@pytest.mark.parametrize("version", ["empty", "version-1"])
def test_log_inbound_on_unmigrated_database_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], version: str
) -> None:
    path = tmp_path / "old.db"
    if version == "empty":
        path.touch()
    else:
        _make_version_1(path)

    code = main(["log-inbound", "--db", str(path), *LOG_ARGS])

    assert code == EXIT_REFUSED
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize("version", ["empty", "version-1"])
def test_review_on_unmigrated_database_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], version: str
) -> None:
    path = tmp_path / "old.db"
    if version == "empty":
        path.touch()
    else:
        _make_version_1(path)

    code = main(["review", "--db", str(path)])

    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert "error:" in captured.err
    assert captured.out == ""


def test_review_out_unwritable_exits_1(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("regular file", encoding="utf-8")
    out_path = blocker / "review.md"

    code = main(["review", "--db", str(db_path), "--out", str(out_path)])

    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert f"error: could not write {out_path}" in captured.err
    assert "review written" not in captured.out
    assert blocker.read_text(encoding="utf-8") == "regular file"
