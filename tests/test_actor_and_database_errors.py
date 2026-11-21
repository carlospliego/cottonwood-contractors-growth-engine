# sir-target: tests/test_actor_and_database_errors.py
"""set-eligibility and mark-reviewed: --actor wiring, a blank actor, and database errors.

F-testing-2: no test exercised the --actor argument of either command, the blank-actor refusal
of mark-reviewed, or the sqlite3.Error refusal of either, so breaking any of them passed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, eligibility, events, hand_review, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _execute(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def _contact(db_path: Path) -> int:
    return _execute(
        db_path,
        "INSERT INTO contacts (name, email, email_norm, eligibility) VALUES (?, ?, ?, 'unknown')",
        ("Pat Lee (TEST)", "pat@acme.example", "pat@acme.example"),
    )


def _lead(db_path: Path) -> int:
    return _execute(
        db_path, "INSERT INTO leads (type, stage) VALUES ('direct_candidate', 'researched')"
    )


def _rows(db_path: Path, sql: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return [tuple(row) for row in conn.execute(sql)]
    finally:
        conn.close()


def _activities(db_path: Path) -> list[tuple[Any, ...]]:
    return _rows(db_path, "SELECT * FROM activities ORDER BY id")


def _contacts(db_path: Path) -> list[tuple[Any, ...]]:
    return _rows(db_path, "SELECT * FROM contacts ORDER BY id")


# --- AC 1: --actor reaches the recorded activity ----------------------------------------------


def test_set_eligibility_records_the_given_actor(db_path: Path) -> None:
    contact = _contact(db_path)
    args = ["set-eligibility", str(contact), "ineligible", "--actor", "founder"]
    assert main([*args, "--db", str(db_path)]) == EXIT_OK
    rows = _rows(db_path, "SELECT type, actor, contact_id FROM activities")
    assert rows == [(eligibility.ACTIVITY_TYPE, "founder", contact)]
    assert events.DEFAULT_ACTOR != "founder"  # so the default could not have passed this test


def test_mark_reviewed_records_the_given_actor(db_path: Path) -> None:
    lead = _lead(db_path)
    args = ["mark-reviewed", str(lead), "relevant", "--reviewer", "founder", "--actor", "founder"]
    assert main([*args, "--db", str(db_path)]) == EXIT_OK
    rows = _rows(db_path, "SELECT type, actor, lead_id FROM activities")
    assert rows == [(hand_review.ACTIVITY_TYPE, "founder", lead)]


# --- AC 2: a blank actor is refused ------------------------------------------------------------


def test_mark_reviewed_refuses_a_blank_actor(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)
    capsys.readouterr()
    args = ["mark-reviewed", str(lead), "relevant", "--reviewer", "founder", "--actor", "   "]
    assert main([*args, "--db", str(db_path)]) == EXIT_REFUSED
    captured = capsys.readouterr()
    assert captured.err.splitlines() == ["error: actor: must not be empty"]
    assert captured.out == ""
    assert _activities(db_path) == []


# --- AC 3: a database error refuses and writes nothing ---------------------------------------


def _fail_after(real: Any) -> Any:
    """Run the real write, then raise a database error, so only the rollback can undo it."""

    def failing(*args: Any, **kwargs: Any) -> Any:
        real(*args, **kwargs)
        raise sqlite3.OperationalError("disk I/O error")

    return failing


def test_set_eligibility_database_error_exits_1_and_changes_nothing(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path)
    contacts_before = _contacts(db_path)
    activities_before = _activities(db_path)
    monkeypatch.setattr(eligibility, "_apply", _fail_after(eligibility._apply))
    capsys.readouterr()
    assert main(["set-eligibility", str(contact), "ineligible", "--db", str(db_path)]) == 1
    captured = capsys.readouterr()
    assert captured.err.splitlines() == ["error: could not update the database: disk I/O error"]
    assert captured.out == ""
    assert _contacts(db_path) == contacts_before
    assert _activities(db_path) == activities_before


def test_mark_reviewed_database_error_exits_1_and_changes_nothing(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _contact(db_path)
    lead = _lead(db_path)
    contacts_before = _contacts(db_path)
    activities_before = _activities(db_path)
    monkeypatch.setattr(hand_review, "_apply", _fail_after(hand_review._apply))
    capsys.readouterr()
    args = ["mark-reviewed", str(lead), "relevant", "--reviewer", "founder"]
    assert main([*args, "--db", str(db_path)]) == 1
    captured = capsys.readouterr()
    assert captured.err.splitlines() == ["error: could not record the review: disk I/O error"]
    assert captured.out == ""
    assert _contacts(db_path) == contacts_before
    assert _activities(db_path) == activities_before
