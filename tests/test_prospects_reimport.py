"""Tests for re-importing research records without duplicates (R-7)."""

from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, events, timeutil
from cottonwood.cli import EXIT_OK, main

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
        "organization": {
            "name": "Acme Dental (TEST)",
            "domain": "acme-dental.example.com",
            "category": "dental",
        },
        "contact": {"name": "Pat Lee (TEST)", "email": "pat@acme-dental.example.com"},
        "property_location": "12 Main St",
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


def _relationship() -> dict[str, Any]:
    return {
        "type": "relationship_prospect",
        "organization": {"name": "Wasatch Property Partners (TEST)"},
        "contact": {"name": "Sam Roe (TEST)", "role": "Property manager"},
        "verified_facts": ["Manages three retail centers"],
        "hypothesis": "Might refer tenants",
        "evidence": [
            {
                "url": "https://wasatch.example.com/team",
                "observed_at": "2026-11-21",
                "observation": "Team page lists Sam Roe as property manager",
            }
        ],
    }


_FILES = iter(range(1, 10_000))


def _import(db_path: Path, tmp_path: Path, records: list[Any]) -> int:
    path = tmp_path / f"research-{next(_FILES)}.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return main(["prospects-import", str(path), "--db", str(db_path)])


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _execute(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _counts(db_path: Path) -> dict[str, int]:
    return {table: int(_rows(db_path, f"SELECT count(*) FROM {table}")[0][0]) for table in TABLES}


def _out(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return capsys.readouterr().out.splitlines()


def _org(db_path: Path, name: str, domain_norm: str | None) -> int:
    _execute(
        db_path,
        "INSERT INTO organizations (name, name_norm, domain_norm, created_at) VALUES (?, ?, ?, ?)",
        (name, name.lower(), domain_norm, NOW),
    )
    return int(_rows(db_path, "SELECT max(id) FROM organizations")[0][0])


# --- AC 1: an identical re-import writes nothing -----------------------------------------


def test_reimporting_the_same_file_changes_nothing(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = [_direct(), _relationship()]
    assert _import(db_path, tmp_path, records) == EXIT_OK
    capsys.readouterr()
    before = _counts(db_path)
    assert _import(db_path, tmp_path, records) == EXIT_OK
    out = _out(capsys)
    assert out == [
        "record 1 (acme-1): matched lead 1",
        "record 2: matched lead 2",
        "imported 0, matched 2, rejected 0",
    ]
    assert _counts(db_path) == before


# --- AC 2: organization matching ---------------------------------------------------------


def test_domain_match_ignores_the_name(db_path: Path, tmp_path: Path) -> None:
    org_id = _org(db_path, "Acme Holdings LLC", "acme.com")
    record = _direct()
    record["organization"] = {"name": "Acme Dental", "domain": "WWW.Acme.com"}
    assert _import(db_path, tmp_path, [record]) == EXIT_OK
    assert _rows(db_path, "SELECT organization_id FROM leads")[0][0] == org_id
    assert _counts(db_path)["organizations"] == 1


def test_name_match_without_a_domain(db_path: Path, tmp_path: Path) -> None:
    org_id = _org(db_path, "Wasatch Property Partners (TEST)", None)
    _execute(
        db_path,
        "UPDATE organizations SET name_norm = 'wasatch property partners test' WHERE id = ?",
        (org_id,),
    )
    record = _relationship()
    record["organization"] = {"name": "  WASATCH Property Partners, (TEST) "}
    assert _import(db_path, tmp_path, [record]) == EXIT_OK
    assert _rows(db_path, "SELECT organization_id FROM leads")[0][0] == org_id
    assert _counts(db_path)["organizations"] == 1


def test_unknown_domain_creates_an_organization_despite_a_name_match(
    db_path: Path, tmp_path: Path
) -> None:
    stored = _org(db_path, "Acme Dental (TEST)", None)
    _execute(
        db_path, "UPDATE organizations SET name_norm = 'acme dental test' WHERE id = ?", (stored,)
    )
    assert _import(db_path, tmp_path, [_direct()]) == EXIT_OK
    org_id = _rows(db_path, "SELECT organization_id FROM leads")[0][0]
    assert org_id != stored
    assert _counts(db_path)["organizations"] == 2


# --- AC 3: contact and lead matching -----------------------------------------------------


def test_contact_matches_on_email_and_ignores_deleted_contacts(
    db_path: Path, tmp_path: Path
) -> None:
    assert _import(db_path, tmp_path, [_direct()]) == EXIT_OK
    second = _direct()
    second["property_location"] = "99 Other Ave"  # a different lead, same contact
    second["contact"]["email"] = " PAT@Acme-Dental.example.com "
    assert _import(db_path, tmp_path, [second]) == EXIT_OK
    leads = _rows(db_path, "SELECT contact_id FROM leads ORDER BY id")
    assert [row[0] for row in leads] == [1, 1]
    assert _counts(db_path)["contacts"] == 1
    _execute(db_path, "UPDATE contacts SET deleted_at = ? WHERE id = 1", (NOW,))
    third = _direct()
    third["property_location"] = "5 Third St"
    assert _import(db_path, tmp_path, [third]) == EXIT_OK
    assert _rows(db_path, "SELECT contact_id FROM leads WHERE id = 3")[0][0] == 2
    assert _counts(db_path)["contacts"] == 2


def test_contact_without_email_matches_on_name_in_the_same_organization(
    db_path: Path, tmp_path: Path
) -> None:
    assert _import(db_path, tmp_path, [_relationship()]) == EXIT_OK
    second = _relationship()
    second["property_location"] = "Fashion Place"
    second["contact"] = {"name": "sam roe test"}
    assert _import(db_path, tmp_path, [second]) == EXIT_OK
    assert [row[0] for row in _rows(db_path, "SELECT contact_id FROM leads ORDER BY id")] == [
        1,
        1,
    ]
    other_org = _relationship()
    other_org["organization"] = {"name": "Other Brokers (TEST)"}
    assert _import(db_path, tmp_path, [other_org]) == EXIT_OK
    assert _counts(db_path)["contacts"] == 2


@pytest.mark.parametrize(
    ("stored", "incoming", "same"),
    [
        (" 12 Main St ", "12 main st", True),
        (None, None, True),
        ("12 Main St", None, False),
        ("12 Main St", "14 Main St", False),
    ],
)
def test_lead_matches_on_trimmed_case_insensitive_location(
    db_path: Path,
    tmp_path: Path,
    stored: str | None,
    incoming: str | None,
    same: bool,
) -> None:
    first = _direct()
    second = _direct()
    for record, location in ((first, stored), (second, incoming)):
        if location is None:
            record.pop("property_location")
        else:
            record["property_location"] = location
    assert _import(db_path, tmp_path, [first]) == EXIT_OK
    assert _import(db_path, tmp_path, [second]) == EXIT_OK
    assert _counts(db_path)["leads"] == (1 if same else 2)


# --- AC 4: new evidence only, stored values kept, differences printed --------------------


def test_matched_record_adds_only_new_evidence_and_prints_differences(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import(db_path, tmp_path, [_direct()]) == EXIT_OK
    capsys.readouterr()
    before = _counts(db_path)
    stored_lead = tuple(_rows(db_path, "SELECT * FROM leads")[0])
    stored_org = tuple(_rows(db_path, "SELECT * FROM organizations")[0])
    stored_contact = tuple(_rows(db_path, "SELECT * FROM contacts")[0])
    again = copy.deepcopy(_direct())
    again["organization"]["category"] = "orthodontics"
    again["evidence"].append(
        {
            "url": "https://permits.example.com/acme",
            "observed_at": "2026-11-25",
            "excerpt": "Tenant improvement permit applied for",
        }
    )
    assert _import(db_path, tmp_path, [again]) == EXIT_OK
    out = _out(capsys)
    assert out == [
        "record 1 (acme-1): matched lead 1 (+1 evidence)",
        "record 1 (acme-1): organization.category differs: stored 'dental',"
        " incoming 'orthodontics' (kept stored)",
        "imported 0, matched 1, rejected 0",
    ]
    after = _counts(db_path)
    assert {table: after[table] - before[table] for table in TABLES} == {
        "organizations": 0,
        "contacts": 0,
        "leads": 0,
        "evidence": 1,
        "activities": 1,
    }
    assert tuple(_rows(db_path, "SELECT * FROM leads")[0]) == stored_lead
    assert tuple(_rows(db_path, "SELECT * FROM organizations")[0]) == stored_org
    assert tuple(_rows(db_path, "SELECT * FROM contacts")[0]) == stored_contact
    activity = _rows(
        db_path,
        f"SELECT * FROM activities AS a WHERE a.type = 'imported'"
        f" AND {events.COUNTED_ACTIVITIES_SQL} ORDER BY a.id DESC",
    )[0]
    payload = json.loads(activity["payload"])
    assert payload.pop("file").startswith("research-")
    assert payload == {
        "record": 1,
        "record_id": "acme-1",
        "created": False,
        "new_evidence": 1,
    }


def test_each_differing_field_is_reported(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import(db_path, tmp_path, [_direct()]) == EXIT_OK
    capsys.readouterr()
    again = _direct()
    again["hypothesis"] = "Needs a full build-out"
    again["verified_facts"] = ["Signed a lease at 12 Main St", "Hiring staff"]
    again["founder_time_h"] = 1.5
    again["is_test"] = True
    again["contact"]["role"] = "Owner"
    assert _import(db_path, tmp_path, [again]) == EXIT_OK
    out = _out(capsys)
    fields = [line.split(": ")[1].split(" differs")[0] for line in out if "differs" in line]
    assert fields == ["contact.role", "hypothesis", "verified_facts", "founder_time_h", "is_test"]
    assert all(line.endswith("(kept stored)") for line in out if "differs" in line)
    assert _rows(db_path, "SELECT hypothesis, is_test FROM leads")[0][:] == (
        "May need a tenant improvement",
        0,
    )


def test_absent_incoming_values_are_not_differences(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import(db_path, tmp_path, [_direct()]) == EXIT_OK
    capsys.readouterr()
    sparse = _direct()
    sparse["organization"].pop("category")
    sparse["hypothesis"] = ""
    sparse["verified_facts"] = []
    assert _import(db_path, tmp_path, [sparse]) == EXIT_OK
    assert not [line for line in _out(capsys) if "differs" in line]


# --- AC 5: the same lead twice in one file -----------------------------------------------


def test_second_record_for_the_same_lead_in_one_file_is_matched(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    second = _direct()
    second["record_id"] = "acme-2"
    assert _import(db_path, tmp_path, [_direct(), second]) == EXIT_OK
    out = _out(capsys)
    assert out[0] == "record 1 (acme-1): created lead 1 (direct_candidate)"
    assert out[1] == "record 2 (acme-2): matched lead 1"
    assert out[-1] == "imported 1, matched 1, rejected 0"
    assert _counts(db_path)["leads"] == 1
    assert _counts(db_path)["evidence"] == 1
