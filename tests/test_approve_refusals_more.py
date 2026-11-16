# sir-target: tests/test_approve_refusals_more.py
"""More approve refusals: lead mismatch, draft directory, blank draft, missing lead, claim lead."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

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
def claims_path(tmp_path: Path) -> Path:
    entry = {
        "id": "service-area",
        "text": "Claim service-area.",
        "status": "unverified",
        "evidence": "Founder email.",
        "verified_by": None,
        "verified_at": None,
    }
    path = tmp_path / "claims.yaml"
    path.write_text(json.dumps({"claims": [entry]}), encoding="utf-8")  # JSON is valid YAML
    return path


def _approve(db_path: Path, *args: str) -> int:
    return main(
        ["approve", *args, "--approver", "Founder", "--reference", REFERENCE, "--db", str(db_path)]
    )


def _activities(db_path: Path) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute("SELECT * FROM activities ORDER BY id"))
    finally:
        conn.close()


def test_lead_approval_with_a_different_lead_is_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _approve(db_path, "lead", "1", "--lead", "2") == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error: lead:")
    assert len(err.splitlines()) == 1
    assert _activities(db_path) == []


def test_draft_that_is_a_directory_is_refused(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "drafts"
    folder.mkdir()
    assert _approve(db_path, "draft", str(folder), "--lead", "1") == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error: draft:")
    assert len(err.splitlines()) == 1
    assert _activities(db_path) == []


def test_blank_draft_item_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _approve(db_path, "draft", "  ", "--lead", "1") == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error: draft:")
    assert len(err.splitlines()) == 1
    assert _activities(db_path) == []


def test_claim_approval_for_a_missing_lead_is_refused(
    db_path: Path, claims_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _approve(db_path, "claim", "service-area", "--lead", "99", "--claims", str(claims_path))
    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error: lead:")
    assert len(err.splitlines()) == 1
    assert _activities(db_path) == []


def test_claim_approval_records_the_lead(db_path: Path, claims_path: Path) -> None:
    code = _approve(db_path, "claim", "service-area", "--lead", "1", "--claims", str(claims_path))
    assert code == EXIT_OK
    rows = _activities(db_path)
    approval = [row for row in rows if row["type"] == "approval"]
    assert len(approval) == 1
    assert approval[0]["lead_id"] == 1
