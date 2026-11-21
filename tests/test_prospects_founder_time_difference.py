# sir-target: tests/test_prospects_founder_time_difference.py
"""A founder_time_h difference line tells stored and incoming apart (F-correctness-8).

{value:g} kept six significant digits, so 1234567 and 1234568 both printed as 1.23457e+06.
"""

from __future__ import annotations

import json
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


def _record(founder_time: float) -> dict[str, Any]:
    return {
        "record_id": "acme-1",
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)", "domain": "acme-dental.example.com"},
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "founder_time_h": founder_time,
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }


def _difference(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    stored: float,
    incoming: float,
) -> str:
    path = tmp_path / "research.json"
    path.write_text(json.dumps([_record(stored)]), encoding="utf-8")
    assert main(["prospects-import", "--db", str(db_path), str(path)]) == EXIT_OK
    path.write_text(json.dumps([_record(incoming)]), encoding="utf-8")
    capsys.readouterr()
    assert main(["prospects-import", "--db", str(db_path), str(path)]) == EXIT_OK
    lines = [
        line for line in capsys.readouterr().out.splitlines() if "founder_time_h differs" in line
    ]
    assert len(lines) == 1, lines
    return lines[0]


def test_large_whole_hours_are_shown_in_full(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    line = _difference(db_path, tmp_path, capsys, 1234567, 1234568)
    assert "stored '1234567'" in line
    assert "incoming '1234568'" in line


def test_a_whole_and_a_fractional_value_are_shown_distinctly(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    line = _difference(db_path, tmp_path, capsys, 2.0, 2.5)
    assert "stored '2'" in line
    assert "incoming '2.5'" in line


def test_values_that_differ_past_six_digits_are_shown_distinctly(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    line = _difference(db_path, tmp_path, capsys, 1.0000001, 1.0000002)
    assert "stored '1.0000001'" in line
    assert "incoming '1.0000002'" in line
