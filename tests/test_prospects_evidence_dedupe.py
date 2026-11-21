# sir-target: tests/test_prospects_evidence_dedupe.py
"""Evidence dedupe keys on url, observed_at, excerpt and observation; CSV re-imports match.

F-testing-3: dropping any part of the key, or a CSV re-import failing to match its leads,
would pass the older tests unnoticed.
"""

from __future__ import annotations

import copy
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

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


def _evidence() -> dict[str, str]:
    """One item carrying every part of the dedupe key."""
    return {
        "url": "https://news.example.com/acme",
        "observed_at": "2026-11-20",
        "excerpt": "Acme Dental will open a second office",
        "observation": "The article is dated this month",
    }


def _record(evidence: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "record_id": "acme-1",
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)", "domain": "acme-dental.example.com"},
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "evidence": evidence,
    }


_FILES = iter(range(1, 10_000))


def _import(db_path: Path, path: Path) -> int:
    return main(["prospects-import", str(path), "--db", str(db_path)])


def _import_json(db_path: Path, tmp_path: Path, records: list[dict[str, Any]]) -> int:
    path = tmp_path / f"research-{next(_FILES)}.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return _import(db_path, path)


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


def _evidence_rows(db_path: Path) -> list[tuple[object, ...]]:
    sql = "SELECT url, observed_at, excerpt, observation FROM evidence ORDER BY id"
    return [tuple(row) for row in _rows(db_path, sql)]


CHANGES = {
    "url": "https://news.example.com/acme-second-office",
    "observed_at": "2026-11-21",
    "excerpt": "Acme Dental confirms a second office",
    "observation": "The article was updated this week",
}


@pytest.mark.parametrize("part", list(CHANGES))
def test_changing_one_key_part_adds_exactly_one_evidence_row(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], part: str
) -> None:
    assert _import_json(db_path, tmp_path, [_record([_evidence()])]) == EXIT_OK
    capsys.readouterr()
    before = _counts(db_path)
    changed = copy.deepcopy(_evidence())
    changed[part] = CHANGES[part]
    assert _import_json(db_path, tmp_path, [_record([changed])]) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "record 1 (acme-1): matched lead 1 (+1 evidence)",
        "imported 0, matched 1, rejected 0",
    ]
    after = _counts(db_path)
    assert after["evidence"] == before["evidence"] + 1
    assert after["leads"] == before["leads"]
    assert _evidence_rows(db_path) == [
        tuple(_evidence().values()),
        tuple(changed.values()),
    ]


def test_an_unchanged_item_adds_no_evidence_row(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import_json(db_path, tmp_path, [_record([_evidence()])]) == EXIT_OK
    capsys.readouterr()
    before = _counts(db_path)
    assert _import_json(db_path, tmp_path, [_record([_evidence()])]) == EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        "record 1 (acme-1): matched lead 1",
        "imported 0, matched 1, rejected 0",
    ]
    assert _counts(db_path) == before


def test_two_identical_items_in_one_record_store_one_evidence_row(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import_json(db_path, tmp_path, [_record([_evidence(), _evidence()])]) == EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        "record 1 (acme-1): created lead 1 (direct_candidate)",
        "imported 1, matched 0, rejected 0",
    ]
    assert _evidence_rows(db_path) == [tuple(_evidence().values())]


CSV_HEADER = [
    "record_id",
    "type",
    "organization_name",
    "organization_domain",
    "contact_name",
    "contact_email",
    "contact_role",
    "property_location",
    "verified_facts",
    "hypothesis",
    "founder_time_h",
    "value_amount",
    "value_basis",
    "evidence_url",
    "evidence_observed_at",
    "evidence_excerpt",
    "evidence_observation",
    "evidence_kind",
]


def _csv_rows() -> list[dict[str, str]]:
    blank = dict.fromkeys(CSV_HEADER, "")
    return [
        {
            **blank,
            "record_id": "acme-1",
            "type": "direct_candidate",
            "organization_name": "Acme Dental (TEST)",
            "organization_domain": "acme-dental.example.com",
            "contact_name": "Pat Lee (TEST)",
            "contact_email": "pat@acme-dental.example.com",
            "property_location": "12 Main St, Sandy",
            "verified_facts": "Signed a lease at 12 Main St\nOpening in March",
            "hypothesis": "May need a tenant improvement",
            "founder_time_h": "0.5",
            "value_amount": "250000.00",
            "value_basis": "founder-estimated",
            "evidence_url": "https://news.example.com/acme",
            "evidence_observed_at": "2026-11-20",
            "evidence_excerpt": "Acme Dental will open a second office",
        },
        {
            **blank,
            "record_id": "birch-1",
            "type": "direct_candidate",
            "organization_name": "Birch Orthodontics (TEST)",
            "verified_facts": "Bought a building on 3rd Ave",
            "hypothesis": "May need a remodel",
            "evidence_url": "https://permits.example.com/birch",
            "evidence_observed_at": "2026-11-19",
            "evidence_observation": "A remodel permit is pending",
        },
        {
            **blank,
            "type": "relationship_prospect",
            "organization_name": "Wasatch Property Partners (TEST)",
            "contact_name": "Sam Roe (TEST)",
            "contact_role": "Property manager",
            "verified_facts": "Manages three retail centers",
            "hypothesis": "Might refer tenants",
            "evidence_url": "https://wasatch.example.com/team",
            "evidence_observed_at": "2026-11-21",
            "evidence_observation": "Team page lists Sam Roe as property manager",
            "evidence_kind": "hypothesis",
        },
    ]


def test_importing_the_same_csv_twice_matches_every_row_and_writes_nothing(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = _csv_rows()
    path = tmp_path / "research.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    assert _import(db_path, path) == EXIT_OK
    assert capsys.readouterr().out.splitlines()[-1] == "imported 3, matched 0, rejected 0"
    before = _counts(db_path)
    assert {"organizations", "contacts", "leads", "evidence", "activities"} <= before.keys()
    assert before["leads"] == len(rows)
    assert _import(db_path, path) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == f"imported 0, matched {len(rows)}, rejected 0"
    assert not [line for line in out if "differs" in line]
    assert _counts(db_path) == before
