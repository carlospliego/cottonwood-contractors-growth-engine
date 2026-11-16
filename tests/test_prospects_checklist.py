"""Tests for checklist answers in research records (R-13): config keys, storage, CSV, re-import."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
TABLES = ("organizations", "contacts", "leads", "evidence", "activities")
CONFIG = (
    "paths:\n  backup_dir: data/backups\n"
    "review:\n"
    "  checklists:\n"
    "    direct_candidate:\n"
    "      - {key: direct_signal, label: Current signal}\n"
    "      - {key: buyer_identified, label: Buyer known}\n"
    "    relationship_prospect:\n"
    "      - {key: firm_relevance, label: Relevant firm}\n"
)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pilot.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    return path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


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


def _write_json(tmp_path: Path, records: list[Any], name: str = "research.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def _import(db_path: Path, path: Path, *extra: str) -> int:
    return main(["prospects-import", str(path), "--db", str(db_path), *extra])


def _rows(db_path: Path, sql: str) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql))
    finally:
        conn.close()


def _checklists(db_path: Path) -> list[object]:
    return [row[0] for row in _rows(db_path, "SELECT checklist FROM leads ORDER BY id")]


def _counts(db_path: Path) -> dict[str, int]:
    return {table: int(_rows(db_path, f"SELECT count(*) FROM {table}")[0][0]) for table in TABLES}


# --- storage -----------------------------------------------------------------------------


def test_checklist_answers_are_stored_as_a_key_sorted_object(db_path: Path, tmp_path: Path) -> None:
    records = [
        _direct(checklist={"direct_signal": "yes", "buyer_identified": "no"}),
        _direct(organization={"name": "Other Co (TEST)"}),
    ]
    assert _import(db_path, _write_json(tmp_path, records)) == EXIT_OK
    assert _checklists(db_path) == ['{"buyer_identified": "no", "direct_signal": "yes"}', None]


def test_relationship_keys_are_checked_against_their_own_queue(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = _direct(type="relationship_prospect", checklist={"firm_relevance": "unknown"})
    bad = _direct(
        type="relationship_prospect",
        organization={"name": "Other Co (TEST)"},
        checklist={"direct_signal": "yes"},
    )
    assert _import(db_path, _write_json(tmp_path, [good, bad])) == EXIT_REFUSED
    assert "rejected record 2: checklist.direct_signal: checklist-item" in (
        capsys.readouterr().err.splitlines()
    )
    assert _checklists(db_path) == ['{"firm_relevance": "unknown"}']


# --- rejections --------------------------------------------------------------------------


def test_answer_outside_yes_no_unknown_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_json(tmp_path, [_direct(checklist={"direct_signal": "maybe"})])
    assert _import(db_path, path) == EXIT_REFUSED
    assert (
        "rejected record 1: checklist.direct_signal: enum" in capsys.readouterr().err.splitlines()
    )
    assert _counts(db_path)["leads"] == 0


def test_key_that_is_not_a_configured_item_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_json(tmp_path, [_direct(checklist={"not_an_item": "yes"})])
    assert _import(db_path, path) == EXIT_REFUSED
    assert "rejected record 1: checklist.not_an_item: checklist-item" in (
        capsys.readouterr().err.splitlines()
    )
    assert _counts(db_path)["leads"] == 0


def test_checklist_that_is_not_an_object_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_json(tmp_path, [_direct(checklist=["direct_signal"])])
    assert _import(db_path, path) == EXIT_REFUSED
    assert "rejected record 1: checklist: type" in capsys.readouterr().err.splitlines()


# --- config loading ----------------------------------------------------------------------


def test_explicit_missing_config_is_an_error(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_json(tmp_path, [_direct()])
    code = _import(db_path, path, "--config", str(tmp_path / "absent.yaml"))
    assert code == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "absent.yaml" in err
    assert _counts(db_path)["leads"] == 0


def test_missing_default_config_accepts_records_without_answers_only(
    db_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(config.CONFIG_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)  # no config/pilot.yaml here: the default config is missing
    plain = _direct()
    answered = _direct(organization={"name": "Other Co (TEST)"}, checklist={"direct_signal": "yes"})
    assert _import(db_path, _write_json(tmp_path, [plain, answered])) == EXIT_REFUSED
    assert "rejected record 2: checklist.direct_signal: checklist-item" in (
        capsys.readouterr().err.splitlines()
    )
    assert _counts(db_path)["leads"] == 1


# --- CSV ---------------------------------------------------------------------------------

CSV_HEADER = [
    "type",
    "organization_name",
    "organization_domain",
    "verified_facts",
    "hypothesis",
    "evidence_url",
    "evidence_observed_at",
    "evidence_excerpt",
    "checklist.direct_signal",
    "checklist.buyer_identified",
]


def test_csv_checklist_columns_store_the_same_answers_as_json(tmp_path: Path) -> None:
    json_db = tmp_path / "json.db"
    csv_db = tmp_path / "csv.db"
    db.migrate(json_db)
    db.migrate(csv_db)
    record = _direct(checklist={"direct_signal": "yes"})
    assert _import(json_db, _write_json(tmp_path, [record])) == EXIT_OK
    path = tmp_path / "research.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerow(
            {
                "type": "direct_candidate",
                "organization_name": "Acme Dental (TEST)",
                "organization_domain": "acme-dental.example.com",
                "verified_facts": "Signed a lease at 12 Main St",
                "hypothesis": "May need a tenant improvement",
                "evidence_url": "https://news.example.com/acme",
                "evidence_observed_at": "2026-11-20",
                "evidence_excerpt": "Acme Dental will open a second office",
                "checklist.direct_signal": "yes",
                "checklist.buyer_identified": "",
            }
        )
    assert _import(csv_db, path) == EXIT_OK
    assert _checklists(csv_db) == _checklists(json_db) == ['{"direct_signal": "yes"}']


def test_csv_column_for_an_unconfigured_item_rejects_the_row(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "research.csv"
    header = [*CSV_HEADER[:8], "checklist.nope"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(
            [
                "direct_candidate",
                "Acme Dental (TEST)",
                "acme-dental.example.com",
                "Signed a lease at 12 Main St",
                "May need a tenant improvement",
                "https://news.example.com/acme",
                "2026-11-20",
                "Acme Dental will open a second office",
                "no",
            ]
        )
    assert _import(db_path, path) == EXIT_REFUSED
    assert "rejected record 1: checklist.nope: checklist-item" in (
        capsys.readouterr().err.splitlines()
    )


# --- re-import ---------------------------------------------------------------------------


def test_reimport_with_a_different_answer_reports_it_and_keeps_stored(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _direct(checklist={"direct_signal": "yes"})
    assert _import(db_path, _write_json(tmp_path, [first], "first.json")) == EXIT_OK
    capsys.readouterr()
    again = _direct(checklist={"direct_signal": "no", "buyer_identified": "yes"})
    assert _import(db_path, _write_json(tmp_path, [again], "again.json")) == EXIT_OK
    out = capsys.readouterr().out.splitlines()
    differs = [line for line in out if "checklist.direct_signal differs" in line]
    assert len(differs) == 1
    assert "kept stored" in differs[0]
    assert "stored 'yes'" in differs[0] and "incoming 'no'" in differs[0]
    assert any("checklist.buyer_identified differs" in line for line in out)
    assert _checklists(db_path) == ['{"direct_signal": "yes"}']


def test_reimport_with_the_same_answers_reports_no_checklist_difference(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _direct(checklist={"direct_signal": "yes"})
    assert _import(db_path, _write_json(tmp_path, [record], "first.json")) == EXIT_OK
    capsys.readouterr()
    assert _import(db_path, _write_json(tmp_path, [record], "again.json")) == EXIT_OK
    assert not [line for line in capsys.readouterr().out.splitlines() if "checklist" in line]


# --- migration ---------------------------------------------------------------------------


def test_fresh_migrate_is_version_5_with_a_checklist_column(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    assert main(["migrate", "--db", str(path)]) == EXIT_OK
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        columns = [row[1] for row in conn.execute("PRAGMA table_info(leads)")]
    finally:
        conn.close()
    assert "checklist" in columns
