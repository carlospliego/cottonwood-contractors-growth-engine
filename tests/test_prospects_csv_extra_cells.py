# sir-target: tests/test_prospects_csv_extra_cells.py
"""A CSV row with more cells than the header is rejected, not truncated (F-correctness-3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
HEADER = (
    "record_id,type,organization_name,verified_facts,hypothesis,"
    "evidence_url,evidence_observed_at,evidence_excerpt"
)
GOOD = (
    "acme-1,direct_candidate,Acme Dental (TEST),Signed a lease,May need a TI,"
    "https://news.example.com/acme,2026-11-20,Acme will open a second office"
)
SECOND = (
    "wasatch-1,direct_candidate,Wasatch Clinic (TEST),Opening in March,Needs a build-out,"
    "https://news.example.com/wasatch,2026-11-21,Wasatch plans a clinic"
)


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


def _import(
    db_path: Path, tmp_path: Path, rows: list[str], capsys: pytest.CaptureFixture[str]
) -> str:
    path = tmp_path / "research.csv"
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    capsys.readouterr()
    main(["prospects-import", "--db", str(db_path), str(path)])
    captured = capsys.readouterr()
    return captured.out + captured.err


def _organizations(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [
            str(row[0])
            for row in conn.execute(
                "SELECT o.name FROM leads l JOIN organizations o ON o.id = l.organization_id"
                " ORDER BY l.id"
            )
        ]
    finally:
        conn.close()


def test_a_row_with_one_extra_cell_is_rejected_and_the_good_row_imports(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _import(db_path, tmp_path, [GOOD, SECOND + ",an extra cell"], capsys)
    assert "rejected record 2 (wasatch-1): row: extra-cells" in output
    assert "imported 1" in output
    assert _organizations(db_path) == ["Acme Dental (TEST)"]


def test_several_extra_cells_are_rejected_too(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _import(db_path, tmp_path, [GOOD + ",x,y"], capsys)
    assert "rejected record 1 (acme-1): row: extra-cells" in output
    assert _organizations(db_path) == []


def test_only_blank_extra_cells_lose_nothing_and_import(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _import(db_path, tmp_path, [GOOD + ",,", SECOND + ", "], capsys)
    assert "rejected" not in output.replace("rejected 0", "")
    assert _organizations(db_path) == ["Acme Dental (TEST)", "Wasatch Clinic (TEST)"]


def test_rows_that_match_the_header_import_as_before(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _import(db_path, tmp_path, [GOOD, SECOND], capsys)
    assert "imported 2" in output
    assert _organizations(db_path) == ["Acme Dental (TEST)", "Wasatch Clinic (TEST)"]
