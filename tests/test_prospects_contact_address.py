"""A researched contact may be only a phone or a postal address, and the address is stored."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
ADDRESS = "4500 S Highland Dr, Holladay, UT 84117"


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


def _record(contact: dict[str, str]) -> dict[str, Any]:
    return {
        "record_id": "holladay-1",
        "type": "direct_candidate",
        "organization": {"name": "Holladay Dental (TEST)"},
        "contact": contact,
        "verified_facts": ["Announced a second office"],
        "hypothesis": "",
        "evidence": [
            {
                "url": "https://news.example.com/holladay",
                "observed_at": "2026-11-20",
                "excerpt": "Holladay Dental will open a second office",
            }
        ],
    }


def _run(db_path: Path, tmp_path: Path, records: list[dict[str, Any]], *extra: str) -> int:
    path = tmp_path / "research.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return main(["prospects-import", str(path), "--db", str(db_path), *extra])


def _contact(db_path: Path) -> sqlite3.Row:
    conn = db.connect(db_path)
    try:
        row = conn.execute("SELECT name, email, phone_e164, address FROM contacts").fetchone()
    finally:
        conn.close()
    assert isinstance(row, sqlite3.Row)
    return row


def test_address_only_contact_is_imported_with_its_address(db_path: Path, tmp_path: Path) -> None:
    contact = {"address": ADDRESS, "source_url": "https://holladay.example.com/contact"}
    assert _run(db_path, tmp_path, [_record(contact)]) == EXIT_OK
    row = _contact(db_path)
    assert row["address"] == ADDRESS
    assert row["name"] is None and row["email"] is None


def test_phone_only_contact_is_imported(db_path: Path, tmp_path: Path) -> None:
    assert _run(db_path, tmp_path, [_record({"phone": "(801) 555-0100"})]) == EXIT_OK
    assert _contact(db_path)["phone_e164"] == "+18015550100"


@pytest.mark.parametrize(
    "contact",
    [{"role": "Office manager"}, {"address": "   "}],
    ids=["role-only", "blank-address"],
)
def test_contact_without_a_route_or_name_is_rejected(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    contact: dict[str, str],
) -> None:
    _run(db_path, tmp_path, [_record(contact)], "--check")
    captured = capsys.readouterr()
    assert "rejected record 1 (holladay-1): contact" in captured.err
    assert captured.out.endswith("check: 0 valid, 1 rejected\n")


def test_csv_contact_address_column_is_imported(db_path: Path, tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    row = {
        "record_id": "holladay-1",
        "type": "direct_candidate",
        "organization_name": "Holladay Dental (TEST)",
        "contact_address": ADDRESS,
        "verified_facts": "Announced a second office",
        "hypothesis": "May need a build-out",
        "evidence_url": "https://news.example.com/holladay",
        "evidence_observed_at": "2026-11-20",
        "evidence_excerpt": "Holladay Dental will open a second office",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    assert main(["prospects-import", str(path), "--db", str(db_path)]) == EXIT_OK
    assert _contact(db_path)["address"] == ADDRESS


def test_reimport_with_a_different_address_reports_the_difference(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(db_path, tmp_path, [_record({"name": "Pat Lee", "address": ADDRESS})]) == EXIT_OK
    capsys.readouterr()
    moved = _record({"name": "Pat Lee", "address": "1 Main St, Sandy, UT"})
    _run(db_path, tmp_path, [moved])
    assert "contact.address" in capsys.readouterr().out
