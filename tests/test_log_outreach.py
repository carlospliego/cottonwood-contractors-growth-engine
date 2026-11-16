"""Tests for log-outreach: record founder sends and flag gate bypasses (R-22)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
EMAIL = "pat@firm.example.com"
REF = "email 2026-11-29 Re: outreach"
SENDER = "Cottonwood Contractors"
POSTAL = "1 Main St, Sandy, UT 84070"
OPT_OUT = "Reply STOP to opt out."
BODY = f"Hello Pat,\n\nA short note.\n\n{SENDER}\n{POSTAL}\n{OPT_OUT}\n"
SOURCE = "https://firm.example.com/team"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@dataclass
class Sent:
    tmp: Path
    db: Path
    sendable: Path
    prepared: int

    def run(self, *args: str) -> int:
        return main([*args, "--db", str(self.db)])

    def log(self, *overrides: str, lead: str = "1", prepared: bool = True) -> int:
        args = ["log-outreach", lead]
        if prepared:
            args += ["--prepared", str(self.prepared)]
        defaults = {
            "--recipient": EMAIL,
            "--source-url": SOURCE,
            "--message": str(self.sendable),
            "--sender": "Founder",
            "--date": "2026-11-30",
            "--provider-message-id": "abc123",
        }
        given = dict(zip(overrides[::2], overrides[1::2], strict=True))
        for flag, value in {**defaults, **given}.items():
            args += [flag, value]
        return self.run(*args)

    def sql(self, statement: str, params: tuple[object, ...] = ()) -> None:
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(statement, params)
            conn.commit()
        finally:
            conn.close()

    def activities(self, kind: str | None = None) -> list[sqlite3.Row]:
        conn = db.connect(self.db)
        try:
            rows = list(conn.execute("SELECT * FROM activities ORDER BY id"))
        finally:
            conn.close()
        return [row for row in rows if kind is None or row["type"] == kind]


def _payload(row: sqlite3.Row) -> dict[str, object]:
    value = json.loads(row["payload"])
    assert isinstance(value, dict)
    return value


@pytest.fixture
def sent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Sent:
    """Lead 1 with a successful prepare-send recorded as activity P."""
    database = tmp_path / "cottonwood.db"
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
    db.migrate(database)
    setup = Sent(tmp_path, database, tmp_path / "send" / "1-1.md", 0)
    setup.sql(
        "INSERT INTO contacts (id, name, email, email_norm, eligibility)"
        " VALUES (1, 'Pat Lee (TEST)', 'Pat@Firm.example.com', ?, 'eligible')",
        (EMAIL,),
    )
    for lead_id in (1, 2):
        setup.sql(
            "INSERT INTO leads (id, type, stage, contact_id) VALUES (?, 'direct_candidate',"
            " 'researched', 1)",
            (lead_id,),
        )
    setup.sql(
        "INSERT INTO evidence (lead_id, url, observed_at, kind)"
        " VALUES (1, 'https://firm.example.com/news', '2026-11-20', 'fact')"
    )
    approve = ["--approver", "Founder", "--reference", REF]
    assert setup.run("approve", "lead", "1", *approve) == EXIT_OK
    assert setup.run("approve", "draft", str(draft), "--lead", "1", *approve) == EXIT_OK
    prepare = ["prepare-send", "1", str(draft), "--claims", str(claims)]
    prepare += ["--out", str(tmp_path / "send"), "--config", str(config)]
    assert setup.run(*prepare) == EXIT_OK
    [prepared] = setup.activities("draft_prepared")
    setup.prepared = int(prepared["id"])
    capsys.readouterr()
    return setup


# --- AC 1: a gated send ---------------------------------------------------------------


def test_a_gated_send_is_recorded(sent: Sent, capsys: pytest.CaptureFixture[str]) -> None:
    before = len(sent.activities())
    assert sent.log() == EXIT_OK
    [row] = sent.activities("sent")
    assert len(sent.activities()) == before + 1
    assert capsys.readouterr().out == f"send recorded: lead 1 (activity {row['id']})\n"
    assert row["lead_id"] == 1
    assert row["contact_id"] == 1
    payload = _payload(row)
    assert payload["prepared"] == sent.prepared
    assert payload["source_url"] == SOURCE
    assert payload["message_sha256"] == hashlib.sha256(sent.sendable.read_bytes()).hexdigest()
    assert payload["sender"] == "Founder"
    assert payload["sent_on"] == "2026-11-30"
    assert payload["provider_message_id"] == "abc123"
    assert payload["recipient_matches"] is True
    assert all("@" not in json.dumps(value) for value in payload.values())
    assert sent.activities("gate_violation") == []


# --- AC 2: bypasses -------------------------------------------------------------------


def _assert_violation(
    sent: Sent, capsys: pytest.CaptureFixture[str], code: int, reason: str
) -> None:
    assert code == EXIT_REFUSED
    [row] = sent.activities("sent")
    [violation] = sent.activities("gate_violation")
    payload = _payload(violation)
    assert payload["sent_activity_id"] == row["id"]
    assert payload["reasons"] == [reason]
    assert f"gate violation: {reason}" in capsys.readouterr().err.splitlines()


def test_no_prepared_is_a_violation(sent: Sent, capsys: pytest.CaptureFixture[str]) -> None:
    _assert_violation(sent, capsys, sent.log(prepared=False), "no prepared draft")


def test_a_refused_preparation_is_not_a_prepared_draft(
    sent: Sent, capsys: pytest.CaptureFixture[str]
) -> None:
    sent.sql(
        "INSERT INTO activities (id, lead_id, type, payload, actor, occurred_at, recorded_at)"
        " VALUES (900, 1, 'prepare_refused', '{}', 'developer', ?, ?)",
        (NOW, NOW),
    )
    sent.prepared = 900
    _assert_violation(sent, capsys, sent.log(), "no prepared draft")


def test_another_leads_prepared_draft_does_not_count(
    sent: Sent, capsys: pytest.CaptureFixture[str]
) -> None:
    _assert_violation(sent, capsys, sent.log(lead="2"), "no prepared draft")


def test_a_different_message_is_a_violation(sent: Sent, capsys: pytest.CaptureFixture[str]) -> None:
    other = sent.tmp / "edited.md"
    other.write_text(BODY + "PS.\n", encoding="utf-8")
    code = sent.log("--message", str(other))
    _assert_violation(sent, capsys, code, "message differs from the prepared draft")


def test_another_recipient_is_a_violation(sent: Sent, capsys: pytest.CaptureFixture[str]) -> None:
    code = sent.log("--recipient", "someone@else.example.com")
    _assert_violation(sent, capsys, code, "recipient differs from the prepared contact")


def test_a_recipient_suppressed_after_preparation_is_a_violation(
    sent: Sent, capsys: pytest.CaptureFixture[str]
) -> None:
    assert sent.run("suppress", EMAIL, "--reason", "asked") == EXIT_OK
    capsys.readouterr()
    _assert_violation(sent, capsys, sent.log(), "recipient suppressed since preparation")


# --- AC 3: refused input --------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "lead", "field"),
    [
        (("--sender", "  "), "1", "sender"),
        (("--source-url", "ftp://x"), "1", "source_url"),
        (("--message", "missing.md"), "1", "message"),
        (("--date", "2026-12-01"), "1", "date"),
        (("--date", "30/11/2026"), "1", "date"),
        (("--recipient", "not-an-email"), "1", "recipient"),
        ((), "99", "lead"),
    ],
)
def test_bad_input_is_refused_and_records_nothing(
    sent: Sent,
    overrides: tuple[str, ...],
    lead: str,
    field: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if overrides[:1] == ("--message",):
        overrides = ("--message", str(sent.tmp / overrides[1]))
    before = len(sent.activities())
    assert sent.log(*overrides, lead=lead) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith(f"error: {field}:")
    assert len(sent.activities()) == before
