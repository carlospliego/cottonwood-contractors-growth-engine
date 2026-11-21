# sir-target: tests/test_prospects_rollback.py
"""A record that fails in the database is undone alone; a database error writes nothing.

F-testing-1: the per-record SAVEPOINT and the prospects-import sqlite3.Error exit path were
untested, so dropping the ROLLBACK TO or the error handling would have passed unnoticed.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, prospects, timeutil
from cottonwood.cli import EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30


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


def _record(key: str, name: str) -> dict[str, Any]:
    return {
        "record_id": key,
        "type": "direct_candidate",
        "organization": {"name": f"{name} (TEST)", "domain": f"{key}.example.com"},
        "contact": {"name": f"Pat {name} (TEST)", "email": f"pat@{key}.example.com"},
        "verified_facts": [f"{name} signed a lease"],
        "hypothesis": "May need a tenant improvement",
        "evidence": [
            {
                "url": f"https://news.example.com/{key}",
                "observed_at": "2026-11-20",
                "excerpt": f"{name} will open a second office",
            }
        ],
    }


_FILES = iter(range(1, 10_000))


def _import(db_path: Path, tmp_path: Path, records: list[dict[str, Any]]) -> int:
    path = tmp_path / f"research-{next(_FILES)}.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return main(["prospects-import", str(path), "--db", str(db_path)])


def _rows(db_path: Path, sql: str) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql))
    finally:
        conn.close()


def _counts(db_path: Path) -> dict[str, int]:
    """Row counts of every table in the database, read from sqlite_master."""
    tables = [
        str(row[0])
        for row in _rows(db_path, "SELECT name FROM sqlite_master WHERE type = 'table'")
        if not str(row[0]).startswith("sqlite_")
    ]
    return {table: int(_rows(db_path, f'SELECT count(*) FROM "{table}"')[0][0]) for table in tables}


def test_a_record_that_fails_after_its_organization_insert_is_undone_alone(
    db_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_insert_lead = prospects._insert_lead
    reached: list[str] = []

    def failing_insert_lead(conn: sqlite3.Connection, record: Any, *args: Any) -> int:
        if record.record_id == "birch-2":
            # The organization (and contact) of this record are already inserted by now.
            reached.append(
                conn.execute(
                    "SELECT name FROM organizations WHERE domain_norm = 'birch-2.example.com'"
                ).fetchone()[0]
            )
            raise sqlite3.IntegrityError("CHECK constraint failed: leads")
        return real_insert_lead(conn, record, *args)

    monkeypatch.setattr(prospects, "_insert_lead", failing_insert_lead)
    records = [
        _record("acme-1", "Acme Dental"),
        _record("birch-2", "Birch Orthodontics"),
        _record("cedar-3", "Cedar Pediatrics"),
    ]
    assert _import(db_path, tmp_path, records) == EXIT_REFUSED
    captured = capsys.readouterr()
    assert reached == ["Birch Orthodontics (TEST)"]
    assert captured.err.splitlines() == ["rejected record 2 (birch-2): record: constraint"]
    assert captured.out.splitlines() == [
        "record 1 (acme-1): created lead 1 (direct_candidate)",
        "record 3 (cedar-3): created lead 2 (direct_candidate)",
        "imported 2, matched 0, rejected 1",
    ]
    names = [
        row[0]
        for row in _rows(
            db_path,
            "SELECT o.name FROM leads AS l JOIN organizations AS o ON o.id = l.organization_id"
            " ORDER BY l.id",
        )
    ]
    assert names == ["Acme Dental (TEST)", "Cedar Pediatrics (TEST)"]
    assert [row[0] for row in _rows(db_path, "SELECT name FROM organizations ORDER BY id")] == [
        "Acme Dental (TEST)",
        "Cedar Pediatrics (TEST)",
    ]
    assert not _rows(db_path, "SELECT 1 FROM contacts WHERE email_norm LIKE '%birch-2%'")
    assert not _rows(db_path, "SELECT 1 FROM evidence WHERE url LIKE '%birch-2%'")
    rejected = [
        json.loads(row[0])
        for row in _rows(db_path, "SELECT payload FROM activities WHERE type = 'import_rejected'")
    ]
    assert [(p["record"], p["record_id"], p["field"], p["rule"]) for p in rejected] == [
        (2, "birch-2", "record", "constraint")
    ]


def test_a_database_error_exits_1_and_writes_nothing(
    db_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _import(db_path, tmp_path, [_record("acme-1", "Acme Dental")]) == 0
    capsys.readouterr()
    before = _counts(db_path)
    assert before["leads"] == 1

    real_insert_evidence = prospects._insert_evidence

    def disk_error_on_cedar(conn: sqlite3.Connection, lead_id: int, item: Any) -> None:
        # birch-2 is fully written and released first, so only the outer rollback removes it.
        if "cedar-3" in item.url:
            raise sqlite3.OperationalError("disk I/O error")
        real_insert_evidence(conn, lead_id, item)

    monkeypatch.setattr(prospects, "_insert_evidence", disk_error_on_cedar)
    records = [_record("birch-2", "Birch Orthodontics"), _record("cedar-3", "Cedar Pediatrics")]
    assert _import(db_path, tmp_path, records) == 1
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("error: could not import into the database")
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert _counts(db_path) == before
