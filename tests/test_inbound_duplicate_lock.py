"""The same-day duplicate check repeats under the write lock before saving (R-2, F-correctness-5).

log-inbound checks for a same-day match, may prompt, then saves. Another writer could save a
matching inquiry in between; log_inquiry therefore takes BEGIN IMMEDIATE first and repeats
the check, refusing when a match appeared that the operator never saw.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest

from cottonwood import db, inbound
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

RECEIVED = "2026-11-20 09:00"
EMAIL = "pat@example.com"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _log(db_path: Path, *args: str) -> int:
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
            RECEIVED,
            "--email",
            EMAIL,
            *args,
        ]
    )


def _lead_count(db_path: Path) -> int:
    conn = db.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM leads").fetchone()[0])
    finally:
        conn.close()


def _save_matching_inquiry_elsewhere(db_path: Path) -> None:
    """Another writer saves a same-day inquiry with the same email."""
    assert _log(db_path, "--confirm-duplicate") == EXIT_OK


def test_match_saved_after_the_check_is_refused(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real = inbound.find_same_day_duplicates
    calls = {"n": 0}

    def racing(
        conn: sqlite3.Connection, email: str | None, phone: str | None, received: str
    ) -> list[int]:
        calls["n"] += 1
        result = real(conn, email, phone, received)
        if calls["n"] == 1:
            # The first check (outside the lock) sees nothing; then the other writer saves.
            monkeypatch.setattr(inbound, "find_same_day_duplicates", real)
            _save_matching_inquiry_elsewhere(db_path)
            monkeypatch.setattr(inbound, "find_same_day_duplicates", racing)
        return result

    monkeypatch.setattr(inbound, "find_same_day_duplicates", racing)
    code = _log(db_path)

    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    assert "possible duplicate lead(s) 1 saved since the check" in err
    assert calls["n"] >= 2  # the check ran again under the lock
    assert _lead_count(db_path) == 1  # only the other writer's inquiry


def test_confirmed_duplicates_still_save(db_path: Path) -> None:
    assert _log(db_path) == EXIT_OK
    assert _log(db_path, "--confirm-duplicate") == EXIT_OK
    assert _lead_count(db_path) == 2


def test_lock_is_taken_before_the_repeated_check(db_path: Path) -> None:
    conn = db.connect(db_path)
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        inquiry = inbound.validate(
            inbound.RawInquiry(
                channel="form",
                received=RECEIVED,
                segment="commercial",
                name=None,
                email=EMAIL,
                phone=None,
                company=None,
                location=None,
                scope=None,
                budget=None,
                is_test=False,
                actor="developer",
            )
        )
        inbound.log_inquiry(conn, inquiry)
    finally:
        conn.close()
    begin = next(i for i, s in enumerate(statements) if s.startswith("BEGIN IMMEDIATE"))
    check = next(i for i, s in enumerate(statements) if "JOIN contacts" in s)
    insert = next(i for i, s in enumerate(statements) if s.startswith("INSERT INTO contacts"))
    assert begin < check < insert


def test_unconfirmed_new_match_raises_and_writes_nothing(db_path: Path) -> None:
    assert _log(db_path) == EXIT_OK
    conn = db.connect(db_path)
    try:
        inquiry = inbound.validate(
            inbound.RawInquiry(
                channel="form",
                received=RECEIVED,
                segment="commercial",
                name=None,
                email=EMAIL,
                phone=None,
                company=None,
                location=None,
                scope=None,
                budget=None,
                is_test=False,
                actor="developer",
            )
        )
        confirmed: Sequence[int] = ()
        with pytest.raises(inbound.DuplicateChangedError) as raised:
            inbound.log_inquiry(conn, inquiry, duplicate_of=confirmed)
        assert raised.value.new == [1]
        assert not conn.in_transaction
    finally:
        conn.close()
    assert _lead_count(db_path) == 1
