"""Tests for the log-inbound same-day duplicate check (R-2)."""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

TABLES = ("leads", "contacts", "organizations", "activities")


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


def _rows(db_path: Path, sql: str) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql))
    finally:
        conn.close()


def _counts(db_path: Path) -> dict[str, int]:
    return {t: _rows(db_path, f"SELECT count(*) FROM {t}")[0][0] for t in TABLES}


def _last_payload(db_path: Path) -> dict[str, object]:
    row = _rows(db_path, "SELECT payload FROM activities ORDER BY id DESC LIMIT 1")[0]
    payload: dict[str, object] = json.loads(row[0])
    return payload


@pytest.fixture
def existing_email(db_path: Path, capsys: pytest.CaptureFixture[str]) -> int:
    assert _log(db_path, "2026-11-16 09:30", "--email", "pat@example.com") == EXIT_OK
    capsys.readouterr()
    return int(_rows(db_path, "SELECT id FROM leads")[0][0])


def test_same_day_email_match_warns_and_refuses_without_confirmation(
    db_path: Path, existing_email: int, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _counts(db_path)
    assert _log(db_path, "2026-11-16 15:00", "--email", "PAT@example.com ") == EXIT_REFUSED
    err = capsys.readouterr().err
    assert "warning: possible duplicate" in err
    assert str(existing_email) in err
    assert "2026-11-16" in err
    assert _counts(db_path) == before


def test_same_day_phone_match_warns_and_refuses(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _log(db_path, "2026-11-16 09:30", "--phone", "(801) 555-0134") == EXIT_OK
    capsys.readouterr()
    before = _counts(db_path)
    assert _log(db_path, "2026-11-16 18:45", "--phone", "801.555.0134") == EXIT_REFUSED
    assert "warning: possible duplicate of lead(s) 1" in capsys.readouterr().err
    assert _counts(db_path) == before


def test_confirm_duplicate_saves_and_records_the_matches(
    db_path: Path, existing_email: int
) -> None:
    assert _log(db_path, "2026-11-16 12:00", "--phone", "8015550199", "--email", "x@y.com") == 0
    second = int(_rows(db_path, "SELECT max(id) FROM leads")[0][0])
    args = ("--email", "pat@example.com", "--phone", "801-555-0199", "--confirm-duplicate")
    assert _log(db_path, "2026-11-16 15:00", *args) == EXIT_OK
    assert _counts(db_path)["leads"] == 3
    assert _last_payload(db_path)["duplicate_of"] == [existing_email, second]


class _TtyStdin(io.StringIO):
    """A stdin that says it is a terminal and holds the operator's typed answer."""

    def isatty(self) -> bool:
        return True


@pytest.mark.parametrize("answer", ["y", "YES", " yes "])
def test_tty_yes_saves(
    db_path: Path,
    existing_email: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    answer: str,
) -> None:
    monkeypatch.setattr(sys, "stdin", _TtyStdin(answer + "\n"))
    assert _log(db_path, "2026-11-16 15:00", "--email", "pat@example.com") == EXIT_OK
    assert capsys.readouterr().err.count("Save anyway? [y/N] ") == 1
    assert _counts(db_path)["leads"] == 2
    assert _last_payload(db_path)["duplicate_of"] == [existing_email]


@pytest.mark.parametrize("answer", ["n", "", "maybe"])
def test_tty_other_answers_refuse(
    db_path: Path, existing_email: int, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    monkeypatch.setattr(sys, "stdin", _TtyStdin(answer + "\n"))
    before = _counts(db_path)
    assert _log(db_path, "2026-11-16 15:00", "--email", "pat@example.com") == EXIT_REFUSED
    assert _counts(db_path) == before


def test_tty_eof_refuses(
    db_path: Path, existing_email: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", _TtyStdin(""))  # readline() at EOF returns ""
    assert _log(db_path, "2026-11-16 15:00", "--email", "pat@example.com") == EXIT_REFUSED
    assert _counts(db_path)["leads"] == 1


def test_different_local_date_with_same_utc_date_is_not_a_duplicate(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 23:30 and 00:30 Denver are 06:30Z and 07:30Z on 2026-11-17.
    assert _log(db_path, "2026-11-16 23:30", "--email", "pat@example.com") == EXIT_OK
    assert _log(db_path, "2026-11-17 00:30", "--email", "pat@example.com") == EXIT_OK
    received = [r[0] for r in _rows(db_path, "SELECT received_at FROM leads ORDER BY id")]
    assert [r[:10] for r in received] == ["2026-11-17", "2026-11-17"]
    assert "warning" not in capsys.readouterr().err


def test_non_matching_same_day_inquiry_saves_without_warning(
    db_path: Path, existing_email: int, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("--email", "sam@example.com", "--phone", "(801) 555-0100")
    assert _log(db_path, "2026-11-16 10:00", *args) == EXIT_OK
    assert "warning" not in capsys.readouterr().err
    assert _last_payload(db_path)["duplicate_of"] == []


def test_name_only_inquiries_never_match(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _log(db_path, "2026-11-16 10:00", "--name", "Pat") == EXIT_OK
    assert _log(db_path, "2026-11-16 11:00", "--name", "Pat") == EXIT_OK
    assert "warning" not in capsys.readouterr().err


def test_confirm_flag_without_match_saves_normally(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _log(db_path, "2026-11-16 10:00", "--email", "a@b.co", "--confirm-duplicate") == 0
    assert "warning" not in capsys.readouterr().err
    assert _last_payload(db_path)["duplicate_of"] == []
