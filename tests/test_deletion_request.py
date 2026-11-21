"""Tests for deletion-request: personal details leave contacts and activity records (R-35, R-17).

A deletion request is the one exception to append-only activities: the contact's details are
removed from its activity payloads, the removal is recorded as a new activity with no personal
data, and the suppression entry is kept (R-24).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, deletion, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
EARLIER = "2026-11-20T15:00:00Z"
NAME = "Jane Quillfeather"
EMAIL = "Jane.Quillfeather@Example.com"
EMAIL_NORM = "jane.quillfeather@example.com"
PHONE = "+17205550143"
NOTE = "Prefers calls after 4pm; gate code 4471 at the Larkspur house"
PERSONAL = (NAME, EMAIL, EMAIL_NORM, PHONE, NOTE)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _seed(db_path: Path, *, suppressed: bool = True) -> tuple[int, int]:
    """A contact with a lead, two activities whose payloads hold its details, and one other."""
    conn = db.connect(db_path)
    try:
        contact = conn.execute(
            "INSERT INTO contacts (name, email, email_norm, phone_e164, role, address)"
            " VALUES (?, ?, ?, ?, 'owner', '12 Larkspur Ln')",
            (NAME, EMAIL, EMAIL_NORM, PHONE),
        ).lastrowid
        lead = conn.execute(
            "INSERT INTO leads (type, contact_id, stage, hypothesis, next_action,"
            " property_location) VALUES ('direct_candidate', ?, 'candidate', ?, ?, ?)",
            (contact, f"{NAME} owns two rentals", f"Call {PHONE}", "Larkspur"),
        ).lastrowid
        other = conn.execute(
            "INSERT INTO contacts (name, email, email_norm) VALUES ('Sam Other', 'sam@x.org',"
            " 'sam@x.org')"
        ).lastrowid
        insert = (
            "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
            " recorded_at) VALUES (?, ?, ?, ?, 'founder', ?, ?)"
        )
        conn.execute(
            insert,
            (
                lead,
                None,
                "walkthrough",
                json.dumps({"note": NOTE, "stage": "walkthrough"}),
                EARLIER,
                EARLIER,
            ),
        )
        conn.execute(
            insert,
            (
                None,
                contact,
                "reply",
                json.dumps(
                    {
                        "note": NOTE,
                        "reply_type": "interested",
                        "from": f"{NAME} <{EMAIL}>",
                        "callback": PHONE,
                    }
                ),
                EARLIER,
                EARLIER,
            ),
        )
        conn.execute(
            insert,
            (
                None,
                other,
                "reply",
                json.dumps({"note": "keep me", "reply_type": "other"}),
                EARLIER,
                EARLIER,
            ),
        )
        if suppressed:
            conn.execute(
                "INSERT INTO suppression (email_norm, reason, source, added_at)"
                " VALUES (?, 'opt_out', 'reply', ?)",
                (EMAIL_NORM, EARLIER),
            )
        conn.commit()
    finally:
        conn.close()
    assert contact is not None and other is not None
    return contact, other


def _rows(db_path: Path, sql: str) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _all_text(db_path: Path, table: str) -> str:
    return "\n".join(
        " ".join("" if value is None else str(value) for value in tuple(row))
        for row in _rows(db_path, f"SELECT * FROM {table}")
    )


def test_deletion_removes_details_from_contacts_and_activities(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact, _ = _seed(db_path)
    suppression_before = [tuple(r) for r in _rows(db_path, "SELECT * FROM suppression")]
    count_before = len(_rows(db_path, "SELECT id FROM activities"))

    code = main(["deletion-request", "--contact", str(contact), "--db", str(db_path)])

    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert f"contact {contact} deleted" in out
    assert "2 activity record(s) redacted" in out
    for table in ("contacts", "activities", "leads"):
        text = _all_text(db_path, table)
        for value in PERSONAL:
            assert value not in text, (table, value)

    removal = _rows(db_path, f"SELECT * FROM activities WHERE type = '{deletion.ACTIVITY_TYPE}'")
    assert len(removal) == 1
    assert removal[0]["contact_id"] == contact
    assert json.loads(removal[0]["payload"]) == {
        "reason": "deletion_request",
        "activities_redacted": 2,
    }
    assert len(_rows(db_path, "SELECT id FROM activities")) == count_before + 1

    # The suppression entry is unchanged (R-24).
    assert [tuple(r) for r in _rows(db_path, "SELECT * FROM suppression")] == suppression_before

    row = _rows(db_path, f"SELECT * FROM contacts WHERE id = {contact}")[0]
    assert row["deleted_at"] == NOW
    assert row["role"] is None and row["address"] is None


def test_other_contacts_activities_are_untouched(db_path: Path) -> None:
    contact, other = _seed(db_path)
    assert main(["deletion-request", "--contact", str(contact), "--db", str(db_path)]) == EXIT_OK
    kept = _rows(db_path, f"SELECT payload FROM activities WHERE contact_id = {other}")
    assert json.loads(kept[0]["payload"]) == {"note": "keep me", "reply_type": "other"}
    assert _rows(db_path, f"SELECT name FROM contacts WHERE id = {other}")[0]["name"] == "Sam Other"


def test_unsuppressed_address_is_suppressed_before_clearing(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contact, _ = _seed(db_path, suppressed=False)
    assert main(["deletion-request", "--contact", str(contact), "--db", str(db_path)]) == EXIT_OK
    assert f"suppressed {EMAIL_NORM}" in capsys.readouterr().out
    rows = _rows(db_path, "SELECT email_norm, reason FROM suppression")
    assert [tuple(r) for r in rows] == [(EMAIL_NORM, "deletion_request")]


def test_append_only_trigger_is_restored(db_path: Path) -> None:
    contact, other = _seed(db_path)
    before = _rows(db_path, "SELECT sql FROM sqlite_master WHERE name = 'activities_no_update'")
    assert main(["deletion-request", "--contact", str(contact), "--db", str(db_path)]) == EXIT_OK
    after = _rows(db_path, "SELECT sql FROM sqlite_master WHERE name = 'activities_no_update'")
    assert [tuple(r) for r in after] == [tuple(r) for r in before]
    conn = db.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(f"UPDATE activities SET payload = '{{}}' WHERE contact_id = {other}")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM activities")
    finally:
        conn.close()


def test_unknown_contact_is_refused_and_changes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(db_path)
    before = _all_text(db_path, "activities")
    assert main(["deletion-request", "--contact", "999", "--db", str(db_path)]) == EXIT_REFUSED
    assert "no contact with id 999" in capsys.readouterr().err
    assert _all_text(db_path, "activities") == before


def test_blank_actor_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    contact, _ = _seed(db_path)
    code = main(
        ["deletion-request", "--contact", str(contact), "--actor", " ", "--db", str(db_path)]
    )
    assert code == EXIT_REFUSED
    assert "actor" in capsys.readouterr().err
    assert NAME in _all_text(db_path, "contacts")


def test_failure_rolls_back_redaction_and_trigger(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contact, _ = _seed(db_path)
    before = _all_text(db_path, "activities")

    def boom(*_: object) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(deletion, "_insert_removal", boom)
    code = main(["deletion-request", "--contact", str(contact), "--db", str(db_path)])
    assert code == EXIT_REFUSED
    assert _all_text(db_path, "activities") == before
    assert NAME in _all_text(db_path, "contacts")
    assert _rows(db_path, "SELECT name FROM sqlite_master WHERE name = 'activities_no_update'")
