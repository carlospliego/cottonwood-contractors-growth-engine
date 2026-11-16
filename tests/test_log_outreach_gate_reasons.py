# sir-target: tests/test_log_outreach_gate_reasons.py
"""log-outreach: several violation reasons together, recipient_matches, suppression boundary."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from cottonwood import db, send

PREPARED_AT = "2026-11-30T10:00:00Z"
EMAIL = "pat@firm.example.com"
OTHER = "someone@else.example.com"
SOURCE = "https://firm.example.com/team"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    (tmp_path / "msg.md").write_text("hello\n", encoding="utf-8")
    digest = send.sha256_file(tmp_path / "msg.md")
    database = tmp_path / "cottonwood.db"
    db.migrate(database)
    connection = db.connect(database)
    connection.execute(
        "INSERT INTO contacts (id, name, email, email_norm, eligibility)"
        " VALUES (1, 'Pat Lee (TEST)', 'Pat@Firm.example.com', ?, 'eligible')",
        (EMAIL,),
    )
    connection.execute(
        "INSERT INTO leads (id, type, stage, contact_id)"
        " VALUES (1, 'direct_candidate', 'researched', 1)"
    )
    connection.execute(
        "INSERT INTO activities (id, lead_id, contact_id, type, payload, actor, occurred_at,"
        " recorded_at) VALUES (7, 1, 1, 'draft_prepared', ?, 'developer', ?, ?)",
        (json.dumps({"sha256": digest}), PREPARED_AT, PREPARED_AT),
    )
    connection.commit()
    return connection


def _suppress(conn: sqlite3.Connection, email: str, added_at: str) -> None:
    conn.execute(
        "INSERT INTO suppression (email_norm, reason, added_at) VALUES (?, 'asked', ?)",
        (email, added_at),
    )
    conn.commit()


def _log(conn: sqlite3.Connection, tmp_path: Path, recipient: str, matching: bool) -> send.Outreach:
    message = tmp_path / "msg.md"
    if not matching:
        message = tmp_path / "edited.md"
        message.write_text("edited\n", encoding="utf-8")
    return send.log_outreach(
        conn,
        1,
        7,
        recipient,
        SOURCE,
        message,
        "Founder",
        "2026-11-30",
        date(2026, 11, 30),
        None,
        "developer",
        "2026-12-01T00:00:00Z",
    )


def _sent_payload(conn: sqlite3.Connection) -> dict[str, object]:
    row = conn.execute("SELECT payload FROM activities WHERE type = 'sent'").fetchone()
    value = json.loads(row["payload"])
    assert isinstance(value, dict)
    return value


def test_every_reason_is_reported_together(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _suppress(conn, OTHER, "2026-11-30T11:00:00Z")
    result = _log(conn, tmp_path, OTHER, matching=False)
    assert result.reasons == (
        send.MESSAGE_DIFFERS,
        send.RECIPIENT_DIFFERS,
        send.RECIPIENT_SUPPRESSED,
    )
    row = conn.execute("SELECT payload FROM activities WHERE type = 'gate_violation'").fetchone()
    assert json.loads(row["payload"])["reasons"] == list(result.reasons)


def test_a_wrong_recipient_is_not_a_match(conn: sqlite3.Connection, tmp_path: Path) -> None:
    result = _log(conn, tmp_path, OTHER, matching=True)
    assert result.reasons == (send.RECIPIENT_DIFFERS,)
    assert _sent_payload(conn)["recipient_matches"] is False


def test_suppression_at_the_instant_of_preparation_is_a_violation(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    _suppress(conn, EMAIL, PREPARED_AT)
    result = _log(conn, tmp_path, EMAIL, matching=True)
    assert result.reasons == (send.RECIPIENT_SUPPRESSED,)


def test_suppression_before_preparation_is_not_a_violation(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    _suppress(conn, EMAIL, "2026-11-30T09:59:59Z")
    result = _log(conn, tmp_path, EMAIL, matching=True)
    assert result.reasons == ()
    assert _sent_payload(conn)["recipient_matches"] is True
