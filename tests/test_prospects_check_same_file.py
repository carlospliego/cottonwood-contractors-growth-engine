# sir-target: tests/test_prospects_check_same_file.py
"""prospects-import --check agrees with the import when records of one file depend on each other.

F-correctness-2: --check only queried the database as it was before the file, while the import
lets a later record see what earlier records of the same file store. A record referred_by the
relationship lead that record 1 creates was accepted by the import but rejected by --check.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
TABLES = ("organizations", "contacts", "leads", "evidence", "activities")


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


def _relationship(**extra: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "relationship_prospect",
        "organization": {"name": "Wasatch Property Partners (TEST)"},
        "contact": {"name": "Sam Roe (TEST)", "role": "Property manager"},
        "verified_facts": ["Manages three retail centers"],
        "hypothesis": "",
        "evidence": [
            {
                "url": "https://wasatch.example.com/team",
                "observed_at": "2026-11-21",
                "observation": "Team page lists Sam Roe as property manager",
                "kind": "hypothesis",
            }
        ],
    }
    record.update(extra)
    return record


def _direct(**extra: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)", "domain": "acme-dental.example.com"},
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
    record.update(extra)
    return record


def _fresh_db(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    db.migrate(path)
    return path


def _counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        return {t: int(conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]) for t in TABLES}
    finally:
        conn.close()


def _check_and_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], records: list[dict[str, Any]]
) -> tuple[list[str], str, list[str], str]:
    """Run --check, then the import on a fresh database; return each one's rejections and
    summary line. Also asserts --check left every table's row count unchanged."""
    path = tmp_path / "research.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    checked_db = _fresh_db(tmp_path, "checked.db")
    before = _counts(checked_db)
    capsys.readouterr()
    main(["prospects-import", str(path), "--db", str(checked_db), "--check"])
    checked = capsys.readouterr()
    assert _counts(checked_db) == before

    imported_db = _fresh_db(tmp_path, "imported.db")
    main(["prospects-import", str(path), "--db", str(imported_db)])
    imported = capsys.readouterr()
    rejected = [line for line in imported.err.splitlines() if line.startswith("rejected")]
    return checked.err.splitlines(), checked.out.strip(), rejected, imported.out.splitlines()[-1]


def test_a_record_referred_by_the_lead_an_earlier_record_creates_passes_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Records 1 and 2 describe the same organization and lead; record 2 names that lead
    # (id 1 on a fresh database) as its referrer, which only exists once record 1 is stored.
    records = [_relationship(), _relationship(referred_by=1)]
    check_lines, check_summary, import_lines, import_summary = _check_and_import(
        tmp_path, capsys, records
    )
    assert import_lines == []
    assert import_summary == "imported 1, matched 1, rejected 0"
    assert check_lines == import_lines
    assert check_summary == "check: 2 valid, 0 rejected"


def test_another_record_referred_by_that_lead_passes_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = [_relationship(), _direct(referred_by=1)]
    check_lines, check_summary, import_lines, import_summary = _check_and_import(
        tmp_path, capsys, records
    )
    assert import_lines == []
    assert check_lines == import_lines
    assert check_summary == "check: 2 valid, 0 rejected"
    assert import_summary == "imported 2, matched 0, rejected 0"


def test_a_referrer_no_record_creates_is_rejected_by_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Record 2 is referred_by lead 2, which record 2 itself would become: a direct candidate,
    # not a relationship prospect, so both reject it. Record 3 is invalid (no evidence).
    invalid = _direct(organization={"name": "Other Co (TEST)"})
    del invalid["evidence"]
    records = [_relationship(), _direct(referred_by=2), invalid]
    check_lines, check_summary, import_lines, import_summary = _check_and_import(
        tmp_path, capsys, records
    )
    assert len(import_lines) == 2
    assert import_lines[0] == "rejected record 2: referred_by: referrer"
    assert import_lines[1].startswith("rejected record 3")
    assert check_lines == import_lines
    assert check_summary == "check: 1 valid, 2 rejected"
    assert import_summary == "imported 1, matched 0, rejected 2"
