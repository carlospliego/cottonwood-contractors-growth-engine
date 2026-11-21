# sir-target: tests/test_prospects_csv_empty_values.py
"""A CSV row can carry an empty hypothesis or no verified facts, as a JSON record can (CCGE-091)."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
HEADER = [
    "type",
    "organization_name",
    "verified_facts",
    "hypothesis",
    "evidence_url",
    "evidence_observed_at",
    "evidence_excerpt",
]
ROW = {
    "type": "direct_candidate",
    "organization_name": "Acme Dental (TEST)",
    "verified_facts": "Signed a lease at 12 Main St",
    "hypothesis": "May need a tenant improvement",
    "evidence_url": "https://news.example.com/acme",
    "evidence_observed_at": "2026-11-20",
    "evidence_excerpt": "Acme Dental will open a second office",
}


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


def _csv(tmp_path: Path, header: list[str], row: dict[str, str]) -> Path:
    path = tmp_path / "research.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)
    return path


def _leads(db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        return [
            (str(row[0]), str(row[1]))
            for row in conn.execute("SELECT hypothesis, verified_facts FROM leads ORDER BY id")
        ]
    finally:
        conn.close()


def _import(db_path: Path, path: Path) -> int:
    return main(["prospects-import", "--db", str(db_path), str(path)])


def test_an_empty_hypothesis_cell_imports_as_empty_text(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _import(db_path, _csv(tmp_path, HEADER, {**ROW, "hypothesis": ""}))
    captured = capsys.readouterr()
    assert code == EXIT_OK, captured.err
    assert "hypothesis: required" not in captured.out + captured.err
    assert _leads(db_path) == [("", json.dumps(["Signed a lease at 12 Main St"]))]


def test_a_blank_hypothesis_cell_also_imports_as_empty_text(db_path: Path, tmp_path: Path) -> None:
    assert _import(db_path, _csv(tmp_path, HEADER, {**ROW, "hypothesis": "   "})) == EXIT_OK
    assert _leads(db_path)[0][0] == ""


def test_an_empty_verified_facts_cell_imports_as_an_empty_list(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _import(db_path, _csv(tmp_path, HEADER, {**ROW, "verified_facts": ""}))
    captured = capsys.readouterr()
    assert code == EXIT_OK, captured.err
    assert "verified_facts: required" not in captured.out + captured.err
    assert _leads(db_path) == [("May need a tenant improvement", "[]")]


def test_both_empty_import(db_path: Path, tmp_path: Path) -> None:
    row = {**ROW, "hypothesis": "", "verified_facts": ""}
    assert _import(db_path, _csv(tmp_path, HEADER, row)) == EXIT_OK
    assert _leads(db_path) == [("", "[]")]


@pytest.mark.parametrize("column", ["hypothesis", "verified_facts"])
def test_a_csv_without_the_column_is_still_a_file_error(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], column: str
) -> None:
    header = [name for name in HEADER if name != column]
    code = _import(db_path, _csv(tmp_path, header, ROW))
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error:")
    assert "CSV header is missing column(s)" in captured.err
    assert column in captured.err
    assert _leads(db_path) == []
