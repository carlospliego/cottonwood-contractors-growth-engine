# sir-target: tests/test_prospects_ascii_numbers.py
"""Research import takes only ASCII digits, with no trailing newline, in numbers and dates.

Python's \\d matches any Unicode digit and $ matches before a final newline, so '100\\n' or
Arabic-Indic '١٠٠' used to pass the value.amount check and be stored (F-correctness-2).
"""

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
ARABIC_INDIC_100 = "١٠٠"  # '١٠٠'


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


def _record(amount: str, observed_at: str = "2026-11-20") -> dict[str, Any]:
    return {
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)"},
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "value": {"amount": amount, "basis": "founder-estimated"},
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": observed_at,
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }


def _import_json(
    db_path: Path, tmp_path: Path, record: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    path = tmp_path / "research.json"
    path.write_text(json.dumps([record]), encoding="utf-8")
    capsys.readouterr()
    code = main(["prospects-import", "--db", str(db_path), str(path)])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def _value_amounts(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [str(row[0]) for row in conn.execute("SELECT value_amount FROM leads ORDER BY id")]
    finally:
        conn.close()


@pytest.mark.parametrize("amount", ["100\n", ARABIC_INDIC_100, "1500.50\n", "١500.50", "15۰۰"])
def test_a_non_ascii_or_newline_amount_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], amount: str
) -> None:
    _code, output = _import_json(db_path, tmp_path, _record(amount), capsys)
    assert "rejected record 1: value.amount: decimal" in output
    assert _value_amounts(db_path) == []


@pytest.mark.parametrize("amount", ["1500.50", "100", "0", "250000.00"])
def test_an_ascii_amount_still_imports(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], amount: str
) -> None:
    code, output = _import_json(db_path, tmp_path, _record(amount), capsys)
    assert code == EXIT_OK, output
    assert _value_amounts(db_path) == [amount]


@pytest.mark.parametrize("observed_at", ["2026-11-20\n", "٢٠٢٦-11-20"])
def test_a_non_ascii_or_newline_date_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], observed_at: str
) -> None:
    _code, output = _import_json(db_path, tmp_path, _record("100", observed_at=observed_at), capsys)
    assert "rejected record 1: evidence[0].observed_at: date" in output
    assert _value_amounts(db_path) == []


def test_a_non_ascii_csv_referred_by_is_not_taken_as_a_lead_id(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header = [
        "type",
        "organization_name",
        "verified_facts",
        "hypothesis",
        "referred_by",
        "evidence_url",
        "evidence_observed_at",
        "evidence_excerpt",
    ]
    row = {
        "type": "direct_candidate",
        "organization_name": "Acme Dental (TEST)",
        "verified_facts": "Signed a lease at 12 Main St",
        "hypothesis": "May need a tenant improvement",
        "referred_by": "١",  # Arabic-Indic '1': int() would read it as lead 1
        "evidence_url": "https://news.example.com/acme",
        "evidence_observed_at": "2026-11-20",
        "evidence_excerpt": "Acme Dental will open a second office",
    }
    path = tmp_path / "research.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerow(row)
    capsys.readouterr()
    main(["prospects-import", "--db", str(db_path), str(path)])
    captured = capsys.readouterr()
    assert "rejected record 1: referred_by: type" in captured.out + captured.err
    assert _value_amounts(db_path) == []
