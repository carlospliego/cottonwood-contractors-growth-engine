# sir-target: tests/test_prospects_reimport_fields.py
"""Every field compared on re-import is reported by its own name and values (F-testing-2).

Each case changes one field of a matched record and expects exactly one difference line,
naming that field with the stored and incoming values, so pairing a field with the wrong column
or dropping it from the comparison fails here.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Callable
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


def _referrer(name: str) -> dict[str, Any]:
    return {
        "type": "relationship_prospect",
        "organization": {"name": name},
        "verified_facts": ["Manages three retail centers"],
        "hypothesis": "Might refer tenants",
        "evidence": [
            {
                "url": f"https://{name.split()[0].lower()}.example.com/team",
                "observed_at": "2026-11-21",
                "observation": "Team page lists a property manager",
            }
        ],
    }


def _direct() -> dict[str, Any]:
    """A direct candidate with every compared field set; referred_by names lead 1."""
    return {
        "record_id": "acme-1",
        "type": "direct_candidate",
        "organization": {
            "name": "Acme Dental (TEST)",
            "domain": "acme-dental.example.com",
            "type": "clinic",
        },
        "contact": {
            "name": "Pat Lee (TEST)",
            "email": "pat@acme-dental.example.com",
            "phone": "+1 801 555 0100",
            "source_url": "https://acme-dental.example.com/team",
        },
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "next_action": "Call Pat about the lease",
        "value": {"amount": "25000", "basis": "founder-estimated"},
        "referred_by": 1,
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }


def _without_domain() -> dict[str, Any]:
    record = _direct()
    del record["organization"]["domain"]
    return record


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


def _set(path: tuple[str, ...], value: object) -> Callable[[dict[str, Any]], None]:
    def change(record: dict[str, Any]) -> None:
        target = record
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


CASES = [
    # (id, base record, change, field, stored, incoming)
    (
        "organization.name",
        _direct,
        _set(("organization", "name"), "Acme Family Dental (TEST)"),
        "organization.name",
        "Acme Dental (TEST)",
        "Acme Family Dental (TEST)",
    ),
    (
        "organization.name-domain-free-case",
        _without_domain,
        _set(("organization", "name"), "ACME DENTAL (TEST)"),
        "organization.name",
        "Acme Dental (TEST)",
        "ACME DENTAL (TEST)",
    ),
    (
        "organization.type",
        _direct,
        _set(("organization", "type"), "dental group"),
        "organization.type",
        "clinic",
        "dental group",
    ),
    (
        "contact.name",
        _direct,
        _set(("contact", "name"), "Patricia Lee (TEST)"),
        "contact.name",
        "Pat Lee (TEST)",
        "Patricia Lee (TEST)",
    ),
    (
        "contact.phone",
        _direct,
        _set(("contact", "phone"), "+1 801 555 0199"),
        "contact.phone",
        "+18015550100",
        "+18015550199",
    ),
    (
        "contact.source_url",
        _direct,
        _set(("contact", "source_url"), "https://acme-dental.example.com/about"),
        "contact.source_url",
        "https://acme-dental.example.com/team",
        "https://acme-dental.example.com/about",
    ),
    (
        "next_action",
        _direct,
        _set(("next_action",), "Email Pat a walkthrough slot"),
        "next_action",
        "Call Pat about the lease",
        "Email Pat a walkthrough slot",
    ),
    (
        "value.amount",
        _direct,
        _set(("value", "amount"), "40000"),
        "value.amount",
        "25000",
        "40000",
    ),
    (
        "value.basis",
        _direct,
        _set(("value", "basis"), "buyer-stated"),
        "value.basis",
        "founder-estimated",
        "buyer-stated",
    ),
    (
        "referred_by",
        _direct,
        _set(("referred_by",), 2),
        "referred_by",
        "1",
        "2",
    ),
]


@pytest.mark.parametrize(
    ("base", "change", "field", "stored", "incoming"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_one_changed_field_gives_one_difference_line(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    base: Callable[[], dict[str, Any]],
    change: Callable[[dict[str, Any]], None],
    field: str,
    stored: str,
    incoming: str,
) -> None:
    referrers = [_referrer("Wasatch Partners (TEST)"), _referrer("Granite Brokers (TEST)")]
    assert _import(db_path, tmp_path, [*referrers, base()]) == EXIT_OK
    capsys.readouterr()
    again = copy.deepcopy(base())
    change(again)
    assert _import(db_path, tmp_path, [again]) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "record 1 (acme-1): matched lead 3",
        f"record 1 (acme-1): {field} differs: stored '{stored}', incoming '{incoming}'"
        " (kept stored)",
        "imported 0, matched 1, rejected 0",
    ]


def test_a_contact_on_a_lead_stored_without_one_is_reported_not_added(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _direct()
    del first["contact"], first["referred_by"]
    assert _import(db_path, tmp_path, [first]) == EXIT_OK
    capsys.readouterr()
    again = _direct()
    del again["referred_by"]
    assert _import(db_path, tmp_path, [again]) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    prefix = "record 1 (acme-1):"
    assert out == [
        f"{prefix} matched lead 1",
        f"{prefix} contact.name differs: stored '', incoming 'Pat Lee (TEST)' (kept stored)",
        f"{prefix} contact.phone differs: stored '', incoming '+18015550100' (kept stored)",
        f"{prefix} contact.source_url differs: stored '',"
        " incoming 'https://acme-dental.example.com/team' (kept stored)",
        "imported 0, matched 1, rejected 0",
    ]
    assert _rows(db_path, "SELECT count(*) FROM contacts")[0][0] == 0
    assert _rows(db_path, "SELECT contact_id FROM leads")[0][0] is None
