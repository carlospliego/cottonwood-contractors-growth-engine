# sir-target: tests/test_prospects_check_stored_referrer.py
"""prospects-import --check and the import agree on a referred_by that names a stored lead.

F-testing-1: the --check tests only covered a referrer that is not a stored relationship
prospect; nothing pinned that a valid stored referrer passes --check and then imports.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

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


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _store_lead(db_path: Path, lead_type: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO leads (type, stage) VALUES (?, 'researched')", (lead_type,)
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def _stored_leads(db_path: Path) -> tuple[int, int]:
    """A stored direct candidate and a stored relationship prospect: (direct id, partner id).

    The partner is not lead 1, so a referrer check that only accepted id 1 would fail."""
    direct = _store_lead(db_path, "direct_candidate")
    partner = _store_lead(db_path, "relationship_prospect")
    assert (direct, partner) == (1, 2)
    return direct, partner


def _referred_record(referred_by: int) -> dict[str, Any]:
    return {
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)", "domain": "acme-dental.example.com"},
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "referred_by": referred_by,
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }


def _write(tmp_path: Path, record: dict[str, Any]) -> Path:
    path = tmp_path / "research.json"
    path.write_text(json.dumps([record]), encoding="utf-8")
    return path


def _counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        return {t: int(conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]) for t in TABLES}
    finally:
        conn.close()


def _run(db_path: Path, path: Path, *extra: str) -> int:
    return main(["prospects-import", str(path), "--db", str(db_path), *extra])


def test_a_stored_relationship_referrer_passes_check_and_imports(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _direct, partner = _stored_leads(db_path)
    path = _write(tmp_path, _referred_record(partner))
    before = _counts(db_path)
    capsys.readouterr()

    assert _run(db_path, path, "--check") == EXIT_OK
    checked = capsys.readouterr()
    assert checked.out == "check: 1 valid, 0 rejected\n"
    assert checked.err == ""
    assert _counts(db_path) == before

    assert _run(db_path, path) == EXIT_OK
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, type, referred_by FROM leads WHERE id NOT IN (1, 2)"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [(3, "direct_candidate", partner)]


def test_a_stored_direct_candidate_referrer_is_rejected_by_check_as_by_the_import(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    direct, _partner = _stored_leads(db_path)
    path = _write(tmp_path, _referred_record(direct))
    capsys.readouterr()

    assert _run(db_path, path, "--check") == EXIT_REFUSED
    checked = capsys.readouterr()
    assert checked.out == "check: 0 valid, 1 rejected\n"
    check_lines = checked.err.splitlines()
    assert check_lines == ["rejected record 1: referred_by: referrer"]

    assert _run(db_path, path) == EXIT_REFUSED
    imported = capsys.readouterr()
    import_lines = [line for line in imported.err.splitlines() if line.startswith("rejected")]
    assert import_lines == check_lines
    assert _counts(db_path)["leads"] == 2
