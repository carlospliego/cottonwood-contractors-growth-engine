# sir-target: tests/test_qualify_payload_values.py
"""The stored R-16 payload for padded and combined --need/--procurement-url (F-testing-5)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
NEED = "needs 4,000 sq ft office TI by March"
URL = "https://bids.example.gov/rfp/123"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    args = ["--channel", "phone", "--received", "2026-11-15 08:00", "--segment", "commercial"]
    assert main(["log-inbound", "--db", str(path), *args, "--name", "Pat Lee"]) == EXIT_OK
    return path


def _qualify(db_path: Path, *extra: str) -> dict[str, object]:
    args = ["1", "remote_screen", "--at", "2026-11-16 09:30", "--stage", "buyer_need_confirmed"]
    assert main(["log-event", "--db", str(db_path), *args, *extra]) == EXIT_OK
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT payload FROM activities WHERE type = 'remote_screen'").fetchone()
        stage = conn.execute("SELECT stage FROM leads WHERE id = 1").fetchone()[0]
    finally:
        conn.close()
    assert stage == "buyer_need_confirmed"
    payload: dict[str, object] = json.loads(row[0])
    return payload


def test_padded_need_is_stored_stripped(db_path: Path) -> None:
    payload = _qualify(db_path, "--need", f"  {NEED}\t ")
    assert payload == {"event": "remote_screen", "need": NEED}


def test_padded_procurement_url_is_stored_stripped(db_path: Path) -> None:
    payload = _qualify(db_path, "--procurement-url", f" \t{URL}  ")
    assert payload == {"event": "remote_screen", "procurement_url": URL}


def test_both_values_are_stored_together(db_path: Path) -> None:
    payload = _qualify(db_path, "--need", NEED, "--procurement-url", URL)
    assert payload == {"event": "remote_screen", "need": NEED, "procurement_url": URL}


def test_both_padded_values_are_stored_stripped(db_path: Path) -> None:
    payload = _qualify(db_path, "--need", f"  {NEED} ", "--procurement-url", f" {URL}\n")
    assert payload == {"event": "remote_screen", "need": NEED, "procurement_url": URL}
