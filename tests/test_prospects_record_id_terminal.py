# sir-target: tests/test_prospects_record_id_terminal.py
"""record_id is a short plain label, and import lines carry no terminal control characters.

F-security-basics-2: record_id was unbounded and unfiltered, yet printed and kept in the
append-only activities log, and difference lines echoed stored and incoming values raw.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
ESC = "\u001b"


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


def _record(record_id: str | None = "acme-1", category: str = "dental") -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "direct_candidate",
        "organization": {
            "name": "Acme Dental (TEST)",
            "domain": "acme-dental.example.com",
            "category": category,
        },
        "verified_facts": ["Signed a lease at 12 Main St"],
        "hypothesis": "May need a tenant improvement",
        "evidence": [
            {
                "url": "https://news.example.com/acme",
                "observed_at": "2026-11-20",
                "excerpt": "Acme Dental will open a second office",
            }
        ],
    }
    if record_id is not None:
        record["record_id"] = record_id
    return record


_FILES = iter(range(1, 10_000))


def _import(db_path: Path, tmp_path: Path, records: list[dict[str, Any]]) -> int:
    path = tmp_path / f"research-{next(_FILES)}.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return main(["prospects-import", str(path), "--db", str(db_path)])


def _rows(db_path: Path, sql: str) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql))
    finally:
        conn.close()


BAD_IDS = {
    "65-characters": "a" * 65,
    "at-sign": "pat@acme",
    "escape": f"acme{ESC}[2J",
    "newline": "acme\n1",
    "null": "acme\u00001",
    "trailing-newline": "acme-1\n",
    "leading-tab": "\tacme-1",
    "trailing-next-line": "acme-1\u0085",
    "leading-unit-separator": "\u001facme-1",
    "delete": "acme\u007f1",
}


@pytest.mark.parametrize("record_id", list(BAD_IDS.values()), ids=list(BAD_IDS))
def test_a_bad_record_id_is_rejected_on_that_field_and_not_logged(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], record_id: str
) -> None:
    assert _import(db_path, tmp_path, [_record(record_id)]) != EXIT_OK
    captured = capsys.readouterr()
    assert captured.err.splitlines() == ["rejected record 1: record_id: record-id"]
    assert record_id not in captured.out + captured.err
    assert _rows(db_path, "SELECT count(*) FROM leads")[0][0] == 0
    payloads = [
        json.loads(row["payload"])
        for row in _rows(db_path, "SELECT payload FROM activities WHERE type = 'import_rejected'")
    ]
    assert len(payloads) == 1
    assert payloads[0]["field"] == "record_id"
    assert payloads[0]["record_id"] is None
    assert record_id not in json.dumps(payloads[0], ensure_ascii=False)
    assert record_id not in json.dumps(payloads[0])


def test_a_64_character_record_id_is_still_accepted(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record_id = "a" * 64
    assert _import(db_path, tmp_path, [_record(record_id)]) == EXIT_OK
    assert f"({record_id})" in capsys.readouterr().out


def test_surrounding_spaces_are_trimmed_from_a_record_id(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import(db_path, tmp_path, [_record("  acme-1 ")]) == EXIT_OK
    assert capsys.readouterr().out.splitlines()[0] == (
        "record 1 (acme-1): created lead 1 (direct_candidate)"
    )


def test_a_plain_record_id_imports_and_is_printed(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import(db_path, tmp_path, [_record("acme-1.v2_x")]) == EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        "record 1 (acme-1.v2_x): created lead 1 (direct_candidate)",
        "imported 1, matched 0, rejected 0",
    ]


def test_an_escape_in_an_incoming_value_is_not_printed(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import(db_path, tmp_path, [_record()]) == EXIT_OK
    capsys.readouterr()
    again = _record(category=f"ortho{ESC}[31mdontics")
    assert _import(db_path, tmp_path, [again]) == EXIT_OK
    out = capsys.readouterr().out
    assert ESC not in out
    differs = [line for line in out.splitlines() if "differs" in line]
    assert differs == [
        "record 1 (acme-1): organization.category differs: stored 'dental',"
        " incoming 'ortho[31mdontics' (kept stored)"
    ]


def test_a_stored_value_with_an_escape_is_not_printed(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _import(db_path, tmp_path, [_record(category=f"den{ESC}]0;x\u0007tal")]) == EXIT_OK
    capsys.readouterr()
    assert _import(db_path, tmp_path, [_record(category="orthodontics")]) == EXIT_OK
    out = capsys.readouterr().out
    assert ESC not in out and "\u0007" not in out
    assert "stored 'den]0;xtal', incoming 'orthodontics'" in out
