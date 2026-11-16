"""Tests for log-reply: replies, opt-out suppression and bounces (R-23)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, EXIT_USAGE, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
EMAIL = "pat@firm.example.com"
REF = "email 2026-11-29 Re: outreach"
SENDER = "Cottonwood Contractors"
POSTAL = "1 Main St, Sandy, UT 84070"
OPT_OUT = "Reply STOP to opt out."
BODY = f"Hello Pat,\n\n{SENDER}\n{POSTAL}\n{OPT_OUT}\n"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """Lead 1 with eligible contact 7 (Pat@Firm.example.com); lead 2 without a contact."""
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO contacts (id, name, email, email_norm, eligibility)"
            " VALUES (7, 'Pat Lee (TEST)', 'Pat@Firm.example.com', ?, 'eligible')",
            (EMAIL,),
        )
        conn.execute(
            "INSERT INTO leads (id, type, stage, contact_id)"
            " VALUES (1, 'direct_candidate', 'researched', 7)"
        )
        conn.execute(
            "INSERT INTO leads (id, type, stage) VALUES (2, 'direct_candidate', 'researched')"
        )
        conn.execute(
            "INSERT INTO evidence (lead_id, url, observed_at, kind)"
            " VALUES (1, 'https://firm.example.com/news', '2026-11-20', 'fact')"
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _run(database: Path, *args: str) -> int:
    return main([*args, "--db", str(database)])


def _activities(database: Path, kind: str | None = None) -> list[sqlite3.Row]:
    conn = db.connect(database)
    try:
        rows = list(conn.execute("SELECT * FROM activities ORDER BY id"))
    finally:
        conn.close()
    return [row for row in rows if kind is None or row["type"] == kind]


def _suppression(database: Path) -> list[sqlite3.Row]:
    conn = db.connect(database)
    try:
        return list(conn.execute("SELECT * FROM suppression"))
    finally:
        conn.close()


def _payload(row: sqlite3.Row) -> dict[str, object]:
    value = json.loads(row["payload"])
    assert isinstance(value, dict)
    return value


# --- AC 1 -----------------------------------------------------------------------------


def test_a_reply_is_recorded(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = _run(
        database, "log-reply", "1", "interested", "--date", "2026-11-30", "--note", "wants a call"
    )
    assert code == EXIT_OK
    [row] = _activities(database, "reply")
    assert capsys.readouterr().out == f"reply recorded: lead 1 interested (activity {row['id']})\n"
    assert row["lead_id"] == 1
    assert _payload(row) == {
        "type": "interested",
        "received_on": "2026-11-30",
        "note": "wants a call",
    }


@pytest.mark.parametrize(
    "kind", ["interested", "not_now", "not_relevant", "referral", "opt_out", "bounce", "other"]
)
def test_every_reply_type_is_accepted(database: Path, kind: str) -> None:
    assert _run(database, "log-reply", "1", kind) == EXIT_OK


def test_an_unknown_reply_type_is_a_usage_error(database: Path) -> None:
    assert _run(database, "log-reply", "1", "maybe") == EXIT_USAGE
    assert _activities(database) == []


# --- AC 2: opt_out --------------------------------------------------------------------


def test_an_opt_out_suppresses_the_address(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(database, "log-reply", "1", "opt_out") == EXIT_OK
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "suppressed: contact 7"
    [entry] = _suppression(database)
    assert entry["email_norm"] == EMAIL
    assert entry["reason"] == "opt-out reply to lead 1"
    assert entry["source"] == "log-reply"
    assert len(_activities(database, "reply")) == 1
    [suppressed] = _activities(database, "suppressed")
    assert suppressed["contact_id"] == 7
    assert "@" not in suppressed["payload"]


def test_an_existing_suppression_is_left_unchanged(database: Path) -> None:
    assert _run(database, "suppress", EMAIL, "--reason", "asked earlier") == EXIT_OK
    [before] = _suppression(database)
    assert _run(database, "log-reply", "1", "opt_out") == EXIT_OK
    [after] = _suppression(database)
    assert dict(after) == dict(before)


def test_after_an_opt_out_prepare_send_fails_suppression(
    database: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "pilot.yaml"
    config.write_text(
        "review:\n  max_evidence_age_days: 30\nsending:\n"
        f"  sender_identity: {json.dumps(SENDER)}\n"
        f"  postal_address: {json.dumps(POSTAL)}\n"
        f"  opt_out_line: {json.dumps(OPT_OUT)}\n",
        encoding="utf-8",
    )
    claims = tmp_path / "claims.yaml"
    claims.write_text(json.dumps({"claims": []}), encoding="utf-8")
    draft = tmp_path / "1-1.md"
    draft.write_text(BODY, encoding="utf-8")
    (tmp_path / "1-1.claims.json").write_text("[]", encoding="utf-8")
    approve = ["--approver", "Founder", "--reference", REF]
    assert _run(database, "approve", "lead", "1", *approve) == EXIT_OK
    assert _run(database, "approve", "draft", str(draft), "--lead", "1", *approve) == EXIT_OK
    assert _run(database, "log-reply", "1", "opt_out") == EXIT_OK
    capsys.readouterr()
    prepare = ["prepare-send", "1", str(draft), "--claims", str(claims)]
    prepare += ["--out", str(tmp_path / "send"), "--config", str(config)]
    assert _run(database, *prepare) == EXIT_REFUSED
    [refused] = _activities(database, "prepare_refused")
    assert _payload(refused)["checks"] == ["suppression"]


# --- AC 3: bounce and refusals --------------------------------------------------------


def test_a_bounce_makes_the_contact_ineligible(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(database, "log-reply", "1", "bounce") == EXIT_OK
    assert "contact 7: eligibility eligible -> ineligible" in capsys.readouterr().out.splitlines()
    conn = db.connect(database)
    try:
        [row] = conn.execute("SELECT eligibility FROM contacts WHERE id = 7").fetchall()
    finally:
        conn.close()
    assert row["eligibility"] == "ineligible"
    assert len(_activities(database, "reply")) == 1
    assert len(_activities(database, "eligibility_set")) == 1


@pytest.mark.parametrize("kind", ["opt_out", "bounce"])
def test_a_lead_without_a_contact_email_is_refused(
    database: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(database, "log-reply", "2", kind) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: contact:")
    assert _activities(database) == []


def test_an_unknown_lead_is_refused(database: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(database, "log-reply", "99", "other") == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: lead:")
    assert _activities(database) == []
