"""Tests for approve: founder approvals with a written-approval reference (R-18)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, gate, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, EXIT_USAGE, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
REFERENCE = "email 2026-11-29 Re: first prospects"


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
    conn = sqlite3.connect(path)
    try:
        conn.execute("INSERT INTO leads (type, stage) VALUES ('direct_candidate', 'researched')")
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def draft(tmp_path: Path) -> Path:
    path = tmp_path / "1-1.md"
    path.write_bytes(b"Hello,\n\nA short note about your building.\n")
    return path


def _approve(db_path: Path, *args: str) -> int:
    return main(["approve", *args, "--db", str(db_path)])


def _activities(db_path: Path) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute("SELECT * FROM activities ORDER BY id"))
    finally:
        conn.close()


def _payload(row: sqlite3.Row) -> dict[str, object]:
    value = json.loads(row["payload"])
    assert isinstance(value, dict)
    return value


def test_lead_approval_is_recorded_with_its_reference(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _approve(db_path, "lead", "1", "--approver", "Founder", "--reference", REFERENCE)
    assert code == EXIT_OK
    assert capsys.readouterr().out == "approval 1 recorded: lead 1 by Founder\n"
    [row] = _activities(db_path)
    assert row["type"] == "approval"
    assert row["lead_id"] == 1
    assert row["actor"] == "developer"
    assert row["recorded_at"] == NOW
    assert _payload(row) == {
        "scope": "lead",
        "item": "1",
        "approver": "Founder",
        "reference": REFERENCE,
        "approved_on": "2026-11-30",
    }


def test_date_sets_the_approval_day(db_path: Path) -> None:
    args = ["lead", "1", "--approver", "Founder", "--reference", REFERENCE]
    assert _approve(db_path, *args, "--date", "2026-11-29") == EXIT_OK
    [row] = _activities(db_path)
    assert _payload(row)["approved_on"] == "2026-11-29"
    assert row["occurred_at"] == "2026-11-29T07:00:00Z"  # Denver midnight in UTC


def test_draft_approval_stores_its_lead_and_digest(
    db_path: Path, draft: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _approve(
        db_path,
        "draft",
        str(draft),
        "--lead",
        "1",
        "--approver",
        "Founder",
        "--reference",
        "email 2026-11-30 Re: draft 1",
    )
    assert code == EXIT_OK
    assert capsys.readouterr().out == f"approval 1 recorded: draft {draft} for lead 1 by Founder\n"
    [row] = _activities(db_path)
    assert row["lead_id"] == 1
    payload = _payload(row)
    assert payload["scope"] == "draft"
    assert payload["item"] == str(draft)
    assert payload["sha256"] == hashlib.sha256(draft.read_bytes()).hexdigest()
    assert payload["reference"] == "email 2026-11-30 Re: draft 1"


@pytest.mark.parametrize(
    ("scope", "item"),
    [("audience", "Salt Lake County property managers"), ("offer", "free walkthrough")],
)
def test_audience_and_offer_need_no_lead(
    db_path: Path, scope: str, item: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _approve(db_path, scope, item, "--approver", "Founder", "--reference", REFERENCE)
    assert code == EXIT_OK
    assert capsys.readouterr().out == f"approval 1 recorded: {scope} {item} by Founder\n"
    [row] = _activities(db_path)
    assert row["lead_id"] is None
    assert _payload(row)["scope"] == scope
    assert _payload(row)["item"] == item


def test_offer_with_a_lead_is_recorded_on_that_lead(db_path: Path) -> None:
    args = ["offer", "free walkthrough", "--lead", "1", "--approver", "Founder"]
    assert _approve(db_path, *args, "--reference", REFERENCE) == EXIT_OK
    [row] = _activities(db_path)
    assert row["lead_id"] == 1


@pytest.mark.parametrize(
    ("args", "prefix"),
    [
        (["lead", "1", "--approver", "Founder"], "error: reference:"),
        (["lead", "1", "--approver", "Founder", "--reference", "   "], "error: reference:"),
        (["lead", "1", "--approver", "  ", "--reference", REFERENCE], "error: approver:"),
        (["lead", "99", "--approver", "Founder", "--reference", REFERENCE], "error: lead:"),
        (["lead", "abc", "--approver", "Founder", "--reference", REFERENCE], "error: lead:"),
        (["draft", "DRAFT", "--approver", "Founder", "--reference", REFERENCE], "error: lead:"),
        (
            ["draft", "MISSING", "--lead", "1", "--approver", "Founder", "--reference", REFERENCE],
            "error: draft:",
        ),
        (["audience", "  ", "--approver", "Founder", "--reference", REFERENCE], "error: item:"),
        (["offer", "", "--approver", "Founder", "--reference", REFERENCE], "error: item:"),
        (
            [
                "lead",
                "1",
                "--approver",
                "Founder",
                "--reference",
                REFERENCE,
                "--date",
                "2026-12-01",
            ],
            "error: date:",
        ),
        (
            [
                "lead",
                "1",
                "--approver",
                "Founder",
                "--reference",
                REFERENCE,
                "--date",
                "30/11/2026",
            ],
            "error: date:",
        ),
        (
            ["offer", "x", "--lead", "99", "--approver", "Founder", "--reference", REFERENCE],
            "error: lead:",
        ),
    ],
)
def test_refusals_name_the_field_and_record_nothing(
    db_path: Path,
    draft: Path,
    tmp_path: Path,
    args: list[str],
    prefix: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resolved = [
        str(draft) if arg == "DRAFT" else str(tmp_path / "missing.md") if arg == "MISSING" else arg
        for arg in args
    ]
    assert _approve(db_path, *resolved) == EXIT_REFUSED
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 1
    assert err[0].startswith(prefix)
    assert _activities(db_path) == []


def test_an_unknown_scope_is_a_usage_error(db_path: Path) -> None:
    args = ["vendor", "x", "--approver", "Founder", "--reference", REFERENCE]
    assert _approve(db_path, *args) == EXIT_USAGE
    assert _activities(db_path) == []


def test_gate_lists_the_five_scopes() -> None:
    assert gate.SCOPES == ("lead", "draft", "claim", "audience", "offer")
