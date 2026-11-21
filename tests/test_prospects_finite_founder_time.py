# sir-target: tests/test_prospects_finite_founder_time.py
"""founder_time_h must be a finite number of hours; Infinity and NaN are rejected (F-correctness-4).

Python's json module reads the bare literals Infinity and NaN, and float() reads CSV 'inf', and the
schema's minimum of 0 lets both through, so the check is a Python rule.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
TABLES = ("organizations", "contacts", "leads", "evidence")


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


def _json_text(founder_time: str) -> str:
    """One record as raw JSON text, so the bare literals Infinity and NaN can be written."""
    return (
        '[{"type": "direct_candidate", "organization": {"name": "Acme Dental (TEST)"},'
        ' "verified_facts": ["Signed a lease"], "hypothesis": "May need a TI",'
        f' "founder_time_h": {founder_time},'
        ' "evidence": [{"url": "https://news.example.com/acme", "observed_at": "2026-11-20",'
        ' "excerpt": "Acme will open a second office"}]}]'
    )


def _run(db_path: Path, path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    capsys.readouterr()
    code = main(["prospects-import", "--db", str(db_path), str(path)])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def _counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        return {t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in TABLES}
    finally:
        conn.close()


def _founder_times(db_path: Path) -> list[float]:
    conn = sqlite3.connect(db_path)
    try:
        return [float(r[0]) for r in conn.execute("SELECT founder_time_h FROM leads ORDER BY id")]
    finally:
        conn.close()


@pytest.mark.parametrize("literal", ["Infinity", "NaN", "-Infinity"])
def test_a_json_non_finite_founder_time_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], literal: str
) -> None:
    path = tmp_path / "research.json"
    path.write_text(_json_text(literal), encoding="utf-8")
    _code, output = _run(db_path, path, capsys)
    assert "rejected record 1: founder_time_h:" in output
    assert _counts(db_path) == dict.fromkeys(TABLES, 0)


@pytest.mark.parametrize("cell", ["inf", "Infinity", "-inf", "1e999"])
def test_a_csv_infinite_founder_time_is_rejected(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], cell: str
) -> None:
    path = tmp_path / "research.csv"
    path.write_text(
        "type,organization_name,verified_facts,hypothesis,founder_time_h,"
        "evidence_url,evidence_observed_at,evidence_excerpt\n"
        f"direct_candidate,Acme Dental (TEST),Signed a lease,May need a TI,{cell},"
        "https://news.example.com/acme,2026-11-20,Acme will open a second office\n",
        encoding="utf-8",
    )
    _code, output = _run(db_path, path, capsys)
    assert "rejected record 1: founder_time_h:" in output
    assert _counts(db_path) == dict.fromkeys(TABLES, 0)


def test_a_finite_founder_time_still_imports(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "research.json"
    path.write_text(_json_text("1.5"), encoding="utf-8")
    code, output = _run(db_path, path, capsys)
    assert code == EXIT_OK, output
    assert _founder_times(db_path) == [1.5]
