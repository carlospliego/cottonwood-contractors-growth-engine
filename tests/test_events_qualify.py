"""Tests for R-16: buyer_need_confirmed only on a stated need or procurement URL."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

AT = "2026-11-16 09:30"
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
    code = main(
        [
            "log-inbound",
            "--db",
            str(path),
            "--channel",
            "phone",
            "--received",
            "2026-11-15 08:00",
            "--segment",
            "commercial",
            "--name",
            "Pat Lee",
        ]
    )
    assert code == EXIT_OK
    return path


def _event(db_path: Path, *args: str) -> int:
    return main(["log-event", "--db", str(db_path), "1", "remote_screen", "--at", AT, *args])


def _rows(db_path: Path, sql: str) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql))
    finally:
        conn.close()


def _stage(db_path: Path) -> str:
    return str(_rows(db_path, "SELECT stage FROM leads WHERE id = 1")[0][0])


def _activity_count(db_path: Path) -> int:
    return int(_rows(db_path, "SELECT count(*) FROM activities")[0][0])


def _event_payload(db_path: Path) -> dict[str, object]:
    row = _rows(db_path, "SELECT payload FROM activities WHERE type = 'remote_screen'")[0]
    payload: dict[str, object] = json.loads(row[0])
    return payload


def test_need_qualifies_and_is_stored(db_path: Path) -> None:
    assert _event(db_path, "--stage", "buyer_need_confirmed", "--need", NEED) == EXIT_OK
    assert _stage(db_path) == "buyer_need_confirmed"
    assert _event_payload(db_path)["need"] == NEED


@pytest.mark.parametrize("url", [URL, "http://bids.example.gov/rfp/9"])
def test_procurement_url_qualifies_and_is_stored(db_path: Path, url: str) -> None:
    assert _event(db_path, "--stage", "buyer_need_confirmed", "--procurement-url", url) == EXIT_OK
    assert _stage(db_path) == "buyer_need_confirmed"
    payload = _event_payload(db_path)
    assert payload["procurement_url"] == url
    assert "need" not in payload


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--need", "   "],
        ["--need", ""],
        ["--procurement-url", "bids.example.gov/rfp"],
        ["--procurement-url", "ftp://x/y"],
        ["--procurement-url", "https://"],
        ["--procurement-url", "   "],
        ["--need", NEED, "--procurement-url", "ftp://x/y"],
    ],
)
def test_qualification_without_evidence_is_refused(
    db_path: Path, extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    before = _activity_count(db_path)
    assert _event(db_path, "--stage", "buyer_need_confirmed", *extra) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")
    assert _activity_count(db_path) == before
    assert _stage(db_path) == "candidate"


@pytest.mark.parametrize(
    "extra",
    [
        ["--need", NEED],
        ["--procurement-url", URL],
        ["--stage", "walkthrough", "--need", NEED],
        ["--stage", "walkthrough", "--procurement-url", URL],
    ],
)
def test_need_or_url_without_qualified_stage_is_refused(
    db_path: Path, extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    before = _activity_count(db_path)
    assert _event(db_path, *extra) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")
    assert _activity_count(db_path) == before
    assert _stage(db_path) == "candidate"
