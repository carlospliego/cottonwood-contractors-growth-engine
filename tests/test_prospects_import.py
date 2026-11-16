"""Tests for prospects-import writing new records (R-5, R-6, R-8, R-12, R-24, R-25)."""

from __future__ import annotations

import copy
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, events, timeutil
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


def _direct() -> dict[str, Any]:
    return {
        "record_id": "acme-1",
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)", "domain": "acme-dental.example.com"},
        "contact": {"name": "Pat Lee (TEST)", "email": "pat@acme-dental.example.com"},
        "property_location": "12 Main St, Sandy",
        "verified_facts": ["Signed a lease at 12 Main St", "Opening in March"],
        "hypothesis": "May need a tenant improvement",
        "founder_time_h": 0.5,
        "value": {"amount": "250000.00", "basis": "founder-estimated"},
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }


def _relationship() -> dict[str, Any]:
    return {
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


def _write_json(tmp_path: Path, records: list[Any], name: str = "research.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def _import(db_path: Path, path: Path) -> int:
    return main(["prospects-import", str(path), "--db", str(db_path)])


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _counts(db_path: Path) -> dict[str, int]:
    return {table: int(_rows(db_path, f"SELECT count(*) FROM {table}")[0][0]) for table in TABLES}


def _counted(db_path: Path, kind: str) -> list[sqlite3.Row]:
    return _rows(
        db_path,
        f"SELECT * FROM activities AS a WHERE a.type = ? AND {events.COUNTED_ACTIVITIES_SQL}",
        (kind,),
    )


# --- AC 1: valid records become leads ----------------------------------------------------


def test_json_records_become_researched_leads(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_json(tmp_path, [_direct(), _relationship()])
    assert _import(db_path, path) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "imported 2, matched 0, rejected 0"
    assert out[0] == "record 1 (acme-1): created lead 1 (direct_candidate)"
    assert out[1] == "record 2: created lead 2 (relationship_prospect)"
    leads = _rows(
        db_path,
        "SELECT leads.*, organizations.name AS org, organizations.domain_norm"
        " FROM leads JOIN organizations ON organizations.id = leads.organization_id"
        " ORDER BY leads.id",
    )
    assert [(lead["type"], lead["stage"]) for lead in leads] == [
        ("direct_candidate", "researched"),
        ("relationship_prospect", "researched"),
    ]
    direct, partner = leads
    assert direct["org"] == "Acme Dental (TEST)"
    assert direct["domain_norm"] == "acme-dental.example.com"
    assert json.loads(direct["verified_facts"]) == [
        "Signed a lease at 12 Main St",
        "Opening in March",
    ]
    assert direct["hypothesis"] == "May need a tenant improvement"
    assert direct["value_amount"] == "250000.00"
    assert direct["value_basis"] == "founder-estimated"
    assert direct["property_location"] == "12 Main St, Sandy"
    assert direct["founder_time_h"] == 0.5
    assert direct["is_test"] == 0
    assert json.loads(partner["verified_facts"]) == ["Manages three retail centers"]
    evidence = _rows(db_path, "SELECT * FROM evidence ORDER BY lead_id")
    assert [(e["lead_id"], e["kind"]) for e in evidence] == [(1, "fact"), (2, "hypothesis")]
    assert evidence[0]["excerpt"] == "Acme Dental will open a second office"
    assert evidence[1]["observation"] == "Team page lists Sam Roe as property manager"
    assert evidence[1]["excerpt"] is None
    imported = _counted(db_path, "imported")
    assert sorted(int(row["lead_id"]) for row in imported) == [1, 2]
    payload = json.loads(imported[0]["payload"])
    assert payload == {
        "file": "research.json",
        "record": 1,
        "record_id": "acme-1",
        "created": True,
        "new_evidence": 1,
    }
    assert imported[0]["occurred_at"] == NOW
    assert imported[0]["actor"] == "developer"


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
    first = {
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
    }
    second = {
        **blank,
        "type": "relationship_prospect",
        "organization_name": "Wasatch Property Partners (TEST)",
        "contact_name": "Sam Roe (TEST)",
        "contact_role": "Property manager",
        "verified_facts": "Manages three retail centers",
        "hypothesis": "",
        "evidence_url": "https://wasatch.example.com/team",
        "evidence_observed_at": "2026-11-21",
        "evidence_observation": "Team page lists Sam Roe as property manager",
        "evidence_kind": "hypothesis",
    }
    return [first, second]


def _snapshot(db_path: Path) -> dict[str, list[tuple[object, ...]]]:
    queries = {
        "organizations": "SELECT name, name_norm, domain_norm, type, category FROM organizations",
        "contacts": "SELECT name, email, email_norm, phone_e164, role, source_url, eligibility"
        " FROM contacts",
        "leads": "SELECT type, stage, property_location, hypothesis, verified_facts, next_action,"
        " founder_time_h, value_amount, value_basis, referred_by, is_test FROM leads",
        "evidence": "SELECT url, observed_at, published_at, excerpt, observation, kind"
        " FROM evidence",
    }
    return {
        table: [tuple(row) for row in _rows(db_path, sql + " ORDER BY id")]
        for table, sql in queries.items()
    }


def test_csv_import_stores_the_same_values_as_json(tmp_path: Path) -> None:
    json_db = tmp_path / "json.db"
    csv_db = tmp_path / "csv.db"
    db.migrate(json_db)
    db.migrate(csv_db)
    # The CSV form cannot carry an empty hypothesis cell (empty = absent), so both use text.
    relationship = _relationship()
    relationship["hypothesis"] = "Might refer tenants"
    rows = _csv_rows()
    rows[1]["hypothesis"] = "Might refer tenants"
    assert _import(json_db, _write_json(tmp_path, [_direct(), relationship])) == EXIT_OK
    csv_path = tmp_path / "research.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    assert _import(csv_db, csv_path) == EXIT_OK
    assert _snapshot(csv_db) == _snapshot(json_db)
    assert len(_snapshot(csv_db)["leads"]) == 2


# --- AC 2: file-level errors write nothing -----------------------------------------------


def _bad_file(tmp_path: Path, case: str) -> Path:
    if case == "txt":
        path = tmp_path / "research.txt"
        path.write_text("[]", encoding="utf-8")
    elif case == "missing":
        path = tmp_path / "missing.json"
    elif case == "invalid-json":
        path = tmp_path / "broken.json"
        path.write_text("[{", encoding="utf-8")
    elif case == "object":
        path = tmp_path / "object.json"
        path.write_text(json.dumps({"records": [_direct()]}), encoding="utf-8")
    else:
        path = tmp_path / "no-url.csv"
        header = [name for name in CSV_HEADER if name != "evidence_url"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(_csv_rows())
    return path


@pytest.mark.parametrize("case", ["txt", "missing", "invalid-json", "object", "csv-no-url"])
def test_file_errors_exit_1_and_write_nothing(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    path = _bad_file(tmp_path, case)
    before = _counts(db_path)
    assert _import(db_path, path) == EXIT_REFUSED
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert str(path) in captured.err
    assert "Traceback" not in captured.err
    assert _counts(db_path) == before


def test_missing_database_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write_json(tmp_path, [_direct()])
    assert _import(tmp_path / "absent.db", path) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")


# --- AC 3: a rejected record writes only its rejection -----------------------------------


@pytest.mark.parametrize("record_id", [None, "bad-2"])
def test_rejected_record_is_named_and_others_import(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    record_id: str | None,
) -> None:
    bad = copy.deepcopy(_direct())
    bad.pop("record_id")
    bad["organization"] = {"name": "Rejected Rentals (TEST)"}
    bad["contact"] = {"name": "Riley Reject (TEST)", "email": "riley@rejected.example.com"}
    bad["evidence"][0] = {"observed_at": "2026-11-20", "excerpt": "Secret rejected excerpt"}
    if record_id is not None:
        bad["record_id"] = record_id
    path = _write_json(tmp_path, [_direct(), bad, _relationship()])
    assert _import(db_path, path) == EXIT_REFUSED
    captured = capsys.readouterr()
    label = "record 2" if record_id is None else f"record 2 ({record_id})"
    assert f"rejected {label}: evidence[0].url: required" in captured.err.splitlines()
    assert captured.out.splitlines()[-1] == "imported 2, matched 0, rejected 1"
    assert [row["type"] for row in _rows(db_path, "SELECT type FROM leads ORDER BY id")] == [
        "direct_candidate",
        "relationship_prospect",
    ]
    assert not _rows(db_path, "SELECT 1 FROM organizations WHERE name LIKE 'Rejected%'")
    assert not _rows(db_path, "SELECT 1 FROM contacts WHERE name LIKE 'Riley%'")
    assert not _rows(db_path, "SELECT 1 FROM evidence WHERE excerpt LIKE 'Secret%'")
    (rejected,) = _counted(db_path, "import_rejected")
    assert rejected["lead_id"] is None
    payload = json.loads(rejected["payload"])
    assert set(payload) == {"file", "record", "record_id", "field", "rule"}
    assert payload == {
        "file": "research.json",
        "record": 2,
        "record_id": record_id,
        "field": "evidence[0].url",
        "rule": "required",
    }
    for text in ("Secret rejected excerpt", "Riley Reject", "riley@rejected.example.com"):
        assert text not in rejected["payload"]


# --- AC 4: suppression and eligibility ---------------------------------------------------


def test_suppressed_contact_is_ineligible_and_others_unknown(db_path: Path, tmp_path: Path) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO suppression (email_norm, reason, added_at) VALUES (?, ?, ?)",
            ("pat@acme-dental.example.com", "opt_out", NOW),
        )
        conn.commit()
    finally:
        conn.close()
    direct = _direct()
    direct["contact"]["email"] = "  PAT@Acme-Dental.example.com "
    assert _import(db_path, _write_json(tmp_path, [direct, _relationship()])) == EXIT_OK
    rows = _rows(db_path, "SELECT email_norm, eligibility FROM contacts ORDER BY id")
    assert [tuple(row) for row in rows] == [
        ("pat@acme-dental.example.com", "ineligible"),
        (None, "unknown"),
    ]
    assert not _rows(db_path, "SELECT 1 FROM contacts WHERE eligibility = 'eligible'")


# --- AC 5: referrals ---------------------------------------------------------------------


def test_referred_by_a_relationship_lead_is_stored(db_path: Path, tmp_path: Path) -> None:
    assert _import(db_path, _write_json(tmp_path, [_relationship()], "partners.json")) == EXIT_OK
    referred = _direct()
    referred["referred_by"] = 1
    assert _import(db_path, _write_json(tmp_path, [referred])) == EXIT_OK
    assert _rows(db_path, "SELECT referred_by FROM leads WHERE id = 2")[0][0] == 1


@pytest.mark.parametrize("referrer", [99, 1])
def test_bad_referrer_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], referrer: int
) -> None:
    assert _import(db_path, _write_json(tmp_path, [_direct()], "direct.json")) == EXIT_OK
    before = _counts(db_path)
    referred = _relationship()
    referred["referred_by"] = referrer  # 99 does not exist; 1 is a direct candidate
    assert _import(db_path, _write_json(tmp_path, [referred])) == EXIT_REFUSED
    captured = capsys.readouterr()
    assert "rejected record 1: referred_by: referrer" in captured.err.splitlines()
    after = _counts(db_path)
    assert {table: after[table] - before[table] for table in TABLES} == {
        "organizations": 0,
        "contacts": 0,
        "leads": 0,
        "evidence": 0,
        "activities": 1,
    }


# --- AC 6: report integration ------------------------------------------------------------


def _metric(text: str, label: str) -> str:
    prefix = f"- {label}: "
    (value,) = [line[len(prefix) :] for line in text.splitlines() if line.startswith(prefix)]
    return value


def test_report_counts_researched_leads_and_rejections(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    test_record = _direct()
    test_record["record_id"] = "test-1"
    test_record["organization"] = {"name": "Labeled Test Co (TEST)"}
    test_record["is_test"] = True
    rejected = _relationship()
    rejected["type"] = "prospect"
    path = _write_json(tmp_path, [_direct(), _relationship(), test_record, rejected])
    assert _import(db_path, path) == EXIT_REFUSED
    assert _rows(db_path, "SELECT is_test FROM leads WHERE id = 3")[0][0] == 1
    capsys.readouterr()
    period = ["--from", "2026-11-30", "--to", "2026-11-30"]
    assert main(["report", "--db", str(db_path), *period]) == EXIT_OK
    text = capsys.readouterr().out
    assert _metric(text, "Researched direct candidates") == "1"
    assert _metric(text, "Researched partner firms") == "1"
    assert _metric(text, "Data-quality failures") == "1"
