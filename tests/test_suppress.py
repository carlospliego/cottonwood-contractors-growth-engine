"""Tests for suppress: an address suppressed without a lead, never changed (R-24)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
CONFIG = (
    "paths:\n  backup_dir: data/backups\n"
    "review:\n"
    "  checklists:\n"
    "    direct_candidate:\n"
    "      - {key: direct_signal, label: Current signal}\n"
)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _suppress(db_path: Path, *args: str) -> int:
    return main(["suppress", *args, "--db", str(db_path)])


def _suppression(db_path: Path) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute("SELECT * FROM suppression ORDER BY email_norm"))
    finally:
        conn.close()


def _record(email: str) -> dict[str, Any]:
    return {
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)"},
        "contact": {"name": "Alice Ray (TEST)", "email": email},
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }


def test_an_address_is_suppressed_normalized(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _suppress(db_path, " Alice@Example.COM ", "--reason", "asked by phone") == EXIT_OK
    assert capsys.readouterr().out == "suppressed alice@example.com\n"
    [row] = _suppression(db_path)
    assert row["email_norm"] == "alice@example.com"
    assert row["reason"] == "asked by phone"
    assert row["source"] == "suppress"
    assert row["added_at"] == NOW


def test_source_is_stored_when_given(db_path: Path) -> None:
    args = ["alice@example.com", "--reason", "asked by phone", "--source", "phone call"]
    assert _suppress(db_path, *args) == EXIT_OK
    [row] = _suppression(db_path)
    assert row["source"] == "phone call"


def test_an_existing_entry_is_reported_and_left_unchanged(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _suppress(db_path, "alice@example.com", "--reason", "asked by phone") == EXIT_OK
    [before] = _suppression(db_path)
    capsys.readouterr()
    assert _suppress(db_path, "alice@example.com", "--reason", "other") == EXIT_OK
    assert capsys.readouterr().out == (
        "alice@example.com already suppressed since 2026-11-30 (asked by phone)\n"
    )
    [after] = _suppression(db_path)
    assert tuple(after) == tuple(before)


@pytest.mark.parametrize(
    ("email", "reason", "prefix"),
    [
        ("alice@example.com", "  ", "error: reason:"),
        ("  ", "x", "error: email:"),
        ("alice", "x", "error: email:"),
        ("a@b@c", "x", "error: email:"),
        ("@example.com", "x", "error: email:"),
        ("alice@", "x", "error: email:"),
    ],
)
def test_refusals_store_nothing(
    db_path: Path, email: str, reason: str, prefix: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _suppress(db_path, email, "--reason", reason) == EXIT_REFUSED
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 1
    assert err[0].startswith(prefix)
    assert _suppression(db_path) == []


def test_a_suppressed_address_is_honored_by_import_and_set_eligibility(
    db_path: Path, tmp_path: Path
) -> None:
    assert _suppress(db_path, "alice@example.com", "--reason", "x") == EXIT_OK
    records = tmp_path / "records.json"
    records.write_text(json.dumps([_record("ALICE@example.com")]), encoding="utf-8")
    assert main(["prospects-import", str(records), "--db", str(db_path)]) == EXIT_OK
    conn = db.connect(db_path)
    try:
        [contact] = list(conn.execute("SELECT id, eligibility FROM contacts"))
    finally:
        conn.close()
    assert contact["eligibility"] == "ineligible"
    code = main(
        [
            "set-eligibility",
            str(contact["id"]),
            "eligible",
            "--source-url",
            "https://news.example.com/acme",
            "--db",
            str(db_path),
        ]
    )
    assert code == EXIT_REFUSED
