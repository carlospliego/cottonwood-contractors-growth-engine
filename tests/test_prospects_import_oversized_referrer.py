# sir-target: tests/test_prospects_import_oversized_referrer.py
"""Regression: an oversized referred_by is a per-record rejection, not a crash."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


def test_oversized_referred_by_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cottonwood.db"
    db.migrate(db_path)
    record = {
        "record_id": "acme-1",
        "type": "direct_candidate",
        "organization": {"name": "Acme Dental (TEST)", "domain": "acme-dental.example.com"},
        "contact": {"name": "Pat Lee (TEST)", "email": "pat@acme-dental.example.com"},
        "property_location": "12 Main St, Sandy",
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "founder_time_h": 0.5,
        "value": {"amount": "250000.00", "basis": "founder-estimated"},
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
        "referred_by": 2**70,
    }
    path = tmp_path / "research.json"
    path.write_text(json.dumps([record]), encoding="utf-8")
    assert main(["prospects-import", str(path), "--db", str(db_path)]) == EXIT_REFUSED
    expected = "rejected record 1 (acme-1): referred_by: referrer"
    assert expected in capsys.readouterr().err.splitlines()
