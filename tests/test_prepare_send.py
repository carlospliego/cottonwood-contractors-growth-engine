"""Tests for prepare-send: a sendable draft only when every R-21 check passes."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
SENDER = "Cottonwood Contractors"
POSTAL = "1 Main St, Sandy, UT 84070"
OPT_OUT = "Reply STOP to opt out."
AD = "Advertisement"
EMAIL = "pat@firm.example.com"
REF = "email 2026-11-29 Re: outreach"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@dataclass
class Setup:
    tmp: Path
    db: Path
    config: Path
    claims: Path
    draft: Path
    claims_list: Path
    out: Path
    contact: int

    def prepare(self, *extra: str, lead: int = 1) -> int:
        return main(
            [
                "prepare-send",
                str(lead),
                str(self.draft),
                "--claims",
                str(self.claims),
                "--out",
                str(self.out),
                "--config",
                str(self.config),
                *extra,
                "--db",
                str(self.db),
            ]
        )

    def run(self, *args: str) -> int:
        return main([*args, "--db", str(self.db)])

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

    def write_config(self, sending: dict[str, str] | None, max_age: int | None = 30) -> None:
        lines = ["paths:", "  backup_dir: data/backups"]
        if max_age is not None:
            lines += ["review:", f"  max_evidence_age_days: {max_age}"]
        if sending:
            lines.append("sending:")
            lines += [f"  {key}: {json.dumps(value)}" for key, value in sending.items()]
        self.config.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_draft(self, body: str) -> None:
        self.draft.write_text(body, encoding="utf-8")

    def approve_draft(self) -> None:
        args = ["approve", "draft", str(self.draft), "--lead", "1", "--approver", "Founder"]
        assert self.run(*args, "--reference", REF) == EXIT_OK


FULL_SENDING = {
    "sender_identity": SENDER,
    "postal_address": POSTAL,
    "opt_out_line": OPT_OUT,
    "ad_identification": AD,
}
BODY = f"{AD}\n\nHello Pat,\n\nA short note.\n\n{SENDER}\n{POSTAL}\n{OPT_OUT}\n"


@pytest.fixture
def ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    """Every R-21 condition met for lead 1."""
    setup = Setup(
        tmp=tmp_path,
        db=tmp_path / "cottonwood.db",
        config=tmp_path / "pilot.yaml",
        claims=tmp_path / "claims.yaml",
        draft=tmp_path / "1-1.md",
        claims_list=tmp_path / "1-1.claims.json",
        out=tmp_path / "send",
        contact=1,
    )
    setup.write_config(FULL_SENDING)
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(setup.config))
    db.migrate(setup.db)
    setup.sql(
        "INSERT INTO contacts (id, name, email, email_norm, eligibility)"
        " VALUES (1, 'Pat Lee (TEST)', 'Pat@Firm.example.com', ?, 'eligible')",
        (EMAIL,),
    )
    setup.sql(
        "INSERT INTO leads (id, type, stage, contact_id) VALUES (1, 'direct_candidate',"
        " 'researched', 1)"
    )
    setup.sql(
        "INSERT INTO evidence (lead_id, url, observed_at, kind)"
        " VALUES (1, 'https://firm.example.com/news', '2026-11-20', 'fact')"
    )
    setup.write_draft(BODY)
    _write_claims(setup, "verified")
    setup.claims_list.write_text(
        json.dumps([{"claim_id": "service-area", "status": "verified"}]), encoding="utf-8"
    )
    assert setup.run("approve", "lead", "1", "--approver", "Founder", "--reference", REF) == 0
    setup.approve_draft()
    claim_args = ["approve", "claim", "service-area", "--approver", "Founder"]
    assert setup.run(*claim_args, "--reference", REF, "--claims", str(setup.claims)) == 0
    return setup


def _write_claims(setup: Setup, status: str, claim_id: str = "service-area") -> None:
    entry: dict[str, object] = {
        "id": claim_id,
        "text": "Serves four counties.",
        "status": status,
        "evidence": "Founder email.",
        "verified_by": "Founder" if status == "verified" else None,
        "verified_at": "2026-11-30" if status == "verified" else None,
    }
    setup.claims.write_text(json.dumps({"claims": [entry]}), encoding="utf-8")


def _payload(row: sqlite3.Row) -> dict[str, object]:
    value = json.loads(row["payload"])
    assert isinstance(value, dict)
    return value


def _refused(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return [line for line in capsys.readouterr().err.splitlines() if line]


def _assert_refused(
    setup: Setup, capsys: pytest.CaptureFixture[str], checks: list[str]
) -> list[str]:
    capsys.readouterr()
    assert setup.prepare() == EXIT_REFUSED
    lines = _refused(capsys)
    assert not (setup.out / setup.draft.name).exists()
    [refused] = setup.activities("prepare_refused")
    assert _payload(refused)["checks"] == checks
    assert setup.activities("draft_prepared") == []
    return lines


# --- AC 1: every check passes ---------------------------------------------------------


def test_a_ready_draft_is_copied_and_recorded(
    ready: Setup, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert ready.prepare() == EXIT_OK
    sendable = ready.out / "1-1.md"
    assert sendable.read_bytes() == ready.draft.read_bytes()
    [prepared] = ready.activities("draft_prepared")
    assert capsys.readouterr().out == (
        f"sendable draft written: {sendable.as_posix()} (prepared {prepared['id']})\n"
    )
    assert prepared["lead_id"] == 1
    assert prepared["contact_id"] == ready.contact
    payload = _payload(prepared)
    assert set(payload) == {
        "draft",
        "sha256",
        "sendable",
        "claim_ids",
        "lead_approval_id",
        "draft_approval_id",
    }
    assert payload["claim_ids"] == ["service-area"]
    assert "@" not in json.dumps(payload)


def test_the_default_output_folder_is_out_send(
    ready: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ready.tmp)
    args = ["prepare-send", "1", str(ready.draft), "--claims", str(ready.claims)]
    assert main([*args, "--config", str(ready.config), "--db", str(ready.db)]) == EXIT_OK
    assert (ready.tmp / "out" / "send" / "1-1.md").read_bytes() == ready.draft.read_bytes()


# --- AC 2: each check alone -----------------------------------------------------------


def test_no_lead_approval_fails_approval(ready: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    [lead_approval] = [
        row for row in ready.activities("approval") if _payload(row)["scope"] == "lead"
    ]
    ready.sql(
        "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at,"
        " voids_activity_id) VALUES (1, 'correction', '{}', 'developer', ?, ?, ?)",
        (NOW, NOW, lead_approval["id"]),
    )
    lines = _assert_refused(ready, capsys, ["approval"])
    assert len(lines) == 1
    assert lines[0].startswith("refused: approval:")


def test_an_edited_draft_fails_approval(ready: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    ready.write_draft(BODY + "One more line.\n")
    lines = _assert_refused(ready, capsys, ["approval"])
    assert lines[0].startswith("refused: approval:")


def test_an_ineligible_contact_fails_eligibility(
    ready: Setup, capsys: pytest.CaptureFixture[str]
) -> None:
    ready.sql("UPDATE contacts SET eligibility = 'ineligible' WHERE id = 1")
    lines = _assert_refused(ready, capsys, ["eligibility"])
    assert lines[0].startswith("refused: eligibility:")


def test_a_suppressed_address_fails_suppression(
    ready: Setup, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ready.run("suppress", EMAIL, "--reason", "asked") == EXIT_OK
    lines = _assert_refused(ready, capsys, ["suppression"])
    assert lines[0].startswith("refused: suppression:")


def test_a_missing_claims_list_fails_claims(
    ready: Setup, capsys: pytest.CaptureFixture[str]
) -> None:
    ready.claims_list.unlink()
    lines = _assert_refused(ready, capsys, ["claims"])
    assert lines[0].startswith("refused: claims:")


@pytest.mark.parametrize("status", ["unverified", "prohibited", "unknown-claim"])
def test_a_claim_that_is_not_verified_fails_claims(
    ready: Setup, status: str, capsys: pytest.CaptureFixture[str]
) -> None:
    if status == "unknown-claim":
        _write_claims(ready, "verified", claim_id="other-claim")
    else:
        _write_claims(ready, status)
    lines = _assert_refused(ready, capsys, ["claims"])
    assert lines[0].startswith("refused: claims:")


@pytest.mark.parametrize("case", ["stale", "none", "unset"])
def test_evidence_must_be_fresh_and_the_age_configured(
    ready: Setup, case: str, capsys: pytest.CaptureFixture[str]
) -> None:
    if case == "stale":
        ready.sql("UPDATE evidence SET observed_at = '2026-10-01'")
    elif case == "none":
        ready.sql("DELETE FROM evidence")
    else:
        ready.write_config(FULL_SENDING, max_age=None)
    lines = _assert_refused(ready, capsys, ["evidence"])
    assert lines[0].startswith("refused: evidence:")


@pytest.mark.parametrize(
    ("missing", "check"),
    [
        (SENDER, "sender_identity"),
        (POSTAL, "postal_address"),
        (OPT_OUT, "opt_out"),
        (AD, "ad_identification"),
    ],
)
def test_the_draft_must_carry_each_configured_value(
    ready: Setup, missing: str, check: str, capsys: pytest.CaptureFixture[str]
) -> None:
    ready.write_draft(BODY.replace(missing, ""))
    ready.approve_draft()  # approve the edited draft so only the content check fails
    lines = _assert_refused(ready, capsys, [check])
    assert lines[0].startswith(f"refused: {check}:")


# --- AC 3: every failure, in order ----------------------------------------------------


def test_every_failed_check_is_named_in_order(
    ready: Setup, capsys: pytest.CaptureFixture[str]
) -> None:
    ready.write_draft("Hello.\n")  # unapproved and missing every configured value
    ready.sql("UPDATE contacts SET eligibility = 'ineligible' WHERE id = 1")
    ready.sql("UPDATE evidence SET observed_at = '2026-10-01'")
    expected = [
        "approval",
        "eligibility",
        "evidence",
        "sender_identity",
        "postal_address",
        "opt_out",
        "ad_identification",
    ]
    lines = _assert_refused(ready, capsys, expected)
    assert [line.split(":")[1].strip() for line in lines] == expected


@pytest.mark.parametrize(
    ("key", "check"), [("sender_identity", "sender_identity"), ("postal_address", "postal_address")]
)
def test_an_unconfigured_sender_or_address_says_not_configured(
    ready: Setup, key: str, check: str, capsys: pytest.CaptureFixture[str]
) -> None:
    ready.write_config({k: v for k, v in FULL_SENDING.items() if k != key})
    lines = _assert_refused(ready, capsys, [check])
    assert "not configured" in lines[0]


def test_without_ad_identification_configured_none_is_required(ready: Setup) -> None:
    ready.write_config({k: v for k, v in FULL_SENDING.items() if k != "ad_identification"})
    ready.write_draft(BODY.replace(AD, ""))
    ready.approve_draft()
    assert ready.prepare() == EXIT_OK


# --- AC 4: unknown lead -----------------------------------------------------------------


def test_an_unknown_lead_records_nothing(ready: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    before = len(ready.activities())
    capsys.readouterr()
    assert ready.prepare(lead=99) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: lead:")
    assert len(ready.activities()) == before


# --- CCGE-134: the checks run inside the write transaction ------------------------------


def test_a_suppression_committed_just_before_the_lock_is_seen(
    ready: Setup, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another writer suppresses the address just before prepare-send takes its write lock.

    The second connection commits its suppression row as the first connection starts
    BEGIN IMMEDIATE; every R-21 check must read after that point and refuse.
    """
    real_connect = db.connect

    def connect_with_a_racing_writer(path: Path) -> sqlite3.Connection:
        conn = real_connect(path)

        def before_statement(statement: str) -> None:
            if statement.strip().upper().startswith("BEGIN IMMEDIATE"):
                conn.set_trace_callback(None)
                other = sqlite3.connect(path, timeout=0.5)
                try:
                    other.execute(
                        "INSERT INTO suppression (email_norm, reason, source, added_at)"
                        " VALUES (?, 'asked', 'suppress', ?)",
                        (EMAIL, NOW),
                    )
                    other.commit()
                finally:
                    other.close()

        conn.set_trace_callback(before_statement)
        return conn

    monkeypatch.setattr(db, "connect", connect_with_a_racing_writer)
    lines = _assert_refused(ready, capsys, ["suppression"])
    assert lines[0].startswith("refused: suppression:")
