# sir-target: tests/test_prospects_import_write_lock.py
"""prospects-import waits for another writer's lock instead of aborting (CCGE-095)."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
HOLD_SECONDS = 0.2


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


def _record() -> dict[str, Any]:
    return {
        "record_id": "lock-1",
        "type": "direct_candidate",
        "organization": {"name": "Lockwood Dental (TEST)", "domain": "lockwood.example.com"},
        "contact": {"name": "Pat Lee (TEST)", "email": "pat@lockwood.example.com"},
        "property_location": "12 Main St, Sandy",
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "founder_time_h": 0.5,
        "value": {"amount": "250000.00", "basis": "founder-estimated"},
        "evidence": [
            {
                "url": "https://news.example.com/lockwood",
                "observed_at": "2026-11-20",
                "excerpt": "Lockwood Dental will open a second office",
            }
        ],
    }


def test_import_waits_for_a_held_write_lock(db_path: Path, tmp_path: Path) -> None:
    research = tmp_path / "research.json"
    research.write_text(json.dumps([_record()]), encoding="utf-8")

    holder = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    holder.isolation_level = None
    holder.execute("BEGIN IMMEDIATE")
    holder.execute(
        "INSERT INTO organizations (name, name_norm, created_at)"
        " VALUES ('Other writer (TEST)', 'other writer test', '2026-11-30T00:00:00Z')"
    )
    release = threading.Timer(HOLD_SECONDS, holder.execute, args=("COMMIT",))
    release.start()
    try:
        code = main(["prospects-import", str(research), "--db", str(db_path)])
    finally:
        release.join()
        holder.close()

    assert code == EXIT_OK
    conn = db.connect(db_path)
    try:
        names = {row[0] for row in conn.execute("SELECT name FROM organizations")}
        leads = conn.execute("SELECT count(*) FROM leads").fetchone()[0]
    finally:
        conn.close()
    assert names == {"Other writer (TEST)", "Lockwood Dental (TEST)"}
    assert leads == 1
