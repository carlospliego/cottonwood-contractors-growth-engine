"""Tests for set-eligibility: source, identity, suppression and deletion checks (R-8, R-24)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, EXIT_USAGE, main

NOW = "2026-12-01T00:00:00Z"
SOURCE = "https://acme.example/team"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


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


def _contact(
    db_path: Path,
    name: str | None = "Pat Lee (TEST)",
    email: str | None = "pat@acme.example",
    eligibility: str = "unknown",
    deleted_at: str | None = None,
) -> int:
    email_norm = None if email is None else email.strip().lower()
    return _execute(
        db_path,
        "INSERT INTO contacts (name, email, email_norm, eligibility, deleted_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, email, email_norm, eligibility, deleted_at),
    )


def _suppress(db_path: Path, email_norm: str) -> None:
    _execute(
        db_path,
        "INSERT INTO suppression (email_norm, reason, added_at) VALUES (?, 'opt-out', ?)",
        (email_norm, NOW),
    )


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _set(db_path: Path, contact: int, value: str, *extra: str) -> int:
    return main(["set-eligibility", str(contact), value, *extra, "--db", str(db_path)])


def _activities(db_path: Path) -> list[sqlite3.Row]:
    return _rows(db_path, "SELECT * FROM activities ORDER BY id")


def _contact_row(db_path: Path, contact: int) -> sqlite3.Row:
    return _rows(db_path, "SELECT * FROM contacts WHERE id = ?", (contact,))[0]


def _errors(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return capsys.readouterr().err.splitlines()


# --- AC 1: eligible with a source URL ----------------------------------------------------


def test_eligible_with_source_url_updates_contact_and_records_basis(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path)

    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_OK

    assert capsys.readouterr().out == f"contact {contact}: eligibility unknown -> eligible\n"
    row = _contact_row(db_path, contact)
    assert row["eligibility"] == "eligible"
    assert row["source_url"] == SOURCE
    activities = _activities(db_path)
    assert len(activities) == 1
    activity = activities[0]
    assert activity["type"] == "eligibility_set"
    assert activity["contact_id"] == contact
    assert activity["lead_id"] is None
    assert activity["occurred_at"] == NOW
    assert json.loads(activity["payload"]) == {
        "from": "unknown",
        "to": "eligible",
        "basis": "public-source-url",
    }
    counted = _rows(
        db_path,
        f"SELECT count(*) FROM activities AS a WHERE {events.COUNTED_ACTIVITIES_SQL}",
    )
    assert counted[0][0] == 1


def test_payload_holds_no_contact_data(db_path: Path) -> None:
    contact = _contact(db_path)
    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_OK
    payload = _activities(db_path)[0]["payload"]
    for text in ("acme.example", "Pat", "pat@"):
        assert text not in payload


# --- AC 2: source URL required and valid -------------------------------------------------


def _unchanged(db_path: Path, contact: int) -> None:
    row = _contact_row(db_path, contact)
    assert row["eligibility"] == "unknown"
    assert row["source_url"] is None
    assert _activities(db_path) == []


def test_eligible_without_source_url_is_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path)
    assert _set(db_path, contact, "eligible") == EXIT_REFUSED
    assert _errors(capsys) == ["error: source-url: required"]
    _unchanged(db_path, contact)


@pytest.mark.parametrize("url", ["ftp://acme.example/x", "acme.example/team", "https://", "  "])
def test_eligible_with_a_bad_source_url_is_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str], url: str
) -> None:
    contact = _contact(db_path)
    assert _set(db_path, contact, "eligible", "--source-url", url) == EXIT_REFUSED
    expected = "error: source-url: required" if not url.strip() else "error: source-url: url"
    assert _errors(capsys) == [expected]
    _unchanged(db_path, contact)


# --- AC 3: suppression -------------------------------------------------------------------


def test_suppressed_address_cannot_become_eligible_or_unknown_but_can_be_ineligible(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path, eligibility="ineligible")
    _suppress(db_path, "pat@acme.example")

    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_REFUSED
    assert _errors(capsys) == ["error: contact: suppressed"]
    assert _set(db_path, contact, "unknown") == EXIT_REFUSED
    assert _errors(capsys) == ["error: contact: suppressed"]
    assert _activities(db_path) == []
    assert _contact_row(db_path, contact)["eligibility"] == "ineligible"


def test_ineligible_on_a_suppressed_address_is_allowed_with_manual_basis(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path)
    _suppress(db_path, "pat@acme.example")

    assert _set(db_path, contact, "ineligible") == EXIT_OK

    assert capsys.readouterr().out == f"contact {contact}: eligibility unknown -> ineligible\n"
    assert _contact_row(db_path, contact)["eligibility"] == "ineligible"
    activities = _activities(db_path)
    assert len(activities) == 1
    assert json.loads(activities[0]["payload"]) == {
        "from": "unknown",
        "to": "ineligible",
        "basis": "manual",
    }


@pytest.mark.parametrize(
    ("stored", "value", "extra"),
    [("unknown", "unknown", ()), ("eligible", "eligible", ("--source-url", SOURCE))],
)
def test_suppressed_address_is_refused_even_when_the_value_is_unchanged(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    stored: str,
    value: str,
    extra: tuple[str, ...],
) -> None:
    contact = _contact(db_path, eligibility=stored)
    _suppress(db_path, "pat@acme.example")
    assert _set(db_path, contact, value, *extra) == EXIT_REFUSED
    assert _errors(capsys) == ["error: contact: suppressed"]
    assert _activities(db_path) == []


def test_suppressed_and_nameless_contact_with_a_source_url_gets_both_lines(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path, name=None)
    _suppress(db_path, "pat@acme.example")
    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_REFUSED
    assert _errors(capsys) == ["error: contact: suppressed", "error: contact: identity"]


def test_unknown_needs_no_source_url_and_has_manual_basis(db_path: Path) -> None:
    contact = _contact(db_path, eligibility="ineligible")
    assert _set(db_path, contact, "unknown") == EXIT_OK
    assert json.loads(_activities(db_path)[0]["payload"])["basis"] == "manual"
    assert _contact_row(db_path, contact)["source_url"] is None


# --- AC 4: deleted contacts and identity -------------------------------------------------


def test_deleted_contact_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    contact = _contact(db_path, deleted_at=NOW)
    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_REFUSED
    assert "error: contact: deleted" in _errors(capsys)
    _unchanged(db_path, contact)


@pytest.mark.parametrize(
    ("name", "email"),
    [(None, "pat@acme.example"), ("  ", "pat@acme.example"), ("Pat Lee (TEST)", None)],
)
def test_contact_without_name_or_email_has_no_clear_identity(
    db_path: Path, capsys: pytest.CaptureFixture[str], name: str | None, email: str | None
) -> None:
    contact = _contact(db_path, name=name, email=email)
    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_REFUSED
    assert _errors(capsys) == ["error: contact: identity"]
    _unchanged(db_path, contact)


def test_shared_email_is_an_ambiguous_identity(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path)
    _contact(db_path, name="Someone Else (TEST)")
    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_REFUSED
    assert _errors(capsys) == ["error: contact: identity"]
    _unchanged(db_path, contact)


def test_a_deleted_contact_with_the_same_email_does_not_make_it_ambiguous(db_path: Path) -> None:
    contact = _contact(db_path)
    _contact(db_path, name=None, email=None, deleted_at=NOW)
    _execute(db_path, "UPDATE contacts SET email_norm = 'pat@acme.example' WHERE id = 2")
    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_OK


def test_every_failed_check_is_named(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    contact = _contact(db_path, name=None)
    _suppress(db_path, "pat@acme.example")
    assert _set(db_path, contact, "eligible") == EXIT_REFUSED
    assert _errors(capsys) == [
        "error: source-url: required",
        "error: contact: suppressed",
        "error: contact: identity",
    ]
    _unchanged(db_path, contact)


# --- AC 5: unknown contact and no-op -----------------------------------------------------


def test_unknown_contact_id_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _set(db_path, 99, "eligible", "--source-url", SOURCE) == EXIT_REFUSED
    assert _errors(capsys) == ["error: no contact 99"]
    assert _activities(db_path) == []


def test_setting_the_current_value_is_a_no_op(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact = _contact(db_path, eligibility="eligible")
    assert _set(db_path, contact, "eligible", "--source-url", SOURCE) == EXIT_OK
    assert capsys.readouterr().out == f"contact {contact}: eligibility already eligible\n"
    assert _activities(db_path) == []
    assert _contact_row(db_path, contact)["source_url"] is None


def test_eligibility_outside_the_three_values_is_a_usage_error(db_path: Path) -> None:
    contact = _contact(db_path)
    assert _set(db_path, contact, "maybe") == EXIT_USAGE
    assert _activities(db_path) == []


def test_missing_database_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["set-eligibility", "1", "ineligible", "--db", str(tmp_path / "absent.db")])
    assert code == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")
