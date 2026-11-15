# sir-target: tests/test_prospects_reimport_is_test.py
"""Omitted is_test on re-import is absent, not a difference (CCGE-090)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


def _record() -> dict[str, Any]:
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


def _import(db_path: Path, tmp_path: Path, name: str, record: dict[str, Any]) -> int:
    path = tmp_path / name
    path.write_text(json.dumps([record]), encoding="utf-8")
    return main(["prospects-import", str(path), "--db", str(db_path)])


def test_omitted_is_test_is_not_a_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cottonwood.db"
    db.migrate(db_path)
    first = _record()
    first["is_test"] = True
    assert _import(db_path, tmp_path, "a.json", first) == EXIT_OK
    capsys.readouterr()
    assert _import(db_path, tmp_path, "b.json", _record()) == EXIT_OK
    assert "is_test" not in capsys.readouterr().out

    explicit = _record()
    explicit["is_test"] = False
    assert _import(db_path, tmp_path, "c.json", explicit) == EXIT_OK
    assert "is_test differs" in capsys.readouterr().out
