"""Tests for prospects-import --check: the import's validation, nothing written (R-25)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
TABLES = ("organizations", "contacts", "leads", "evidence", "activities")
CONFIG = (
    "paths:\n  backup_dir: data/backups\n"
    "review:\n"
    "  checklists:\n"
    "    direct_candidate:\n"
    "      - {key: direct_signal, label: Current signal}\n"
)
CONFIG_WITHOUT_SIGNAL = (
    "paths:\n  backup_dir: data/backups\n"
    "review:\n"
    "  checklists:\n"
    "    direct_candidate:\n"
    "      - {key: buyer_identified, label: Buyer known}\n"
)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pilot.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    return path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _record(name: str = "Acme Dental (TEST)", **extra: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "direct_candidate",
        "organization": {"name": name},
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
    record.update(extra)
    return record


def _write(tmp_path: Path, records: object, name: str = "research.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def _run(db_path: Path, path: Path, *extra: str) -> int:
    return main(["prospects-import", str(path), "--db", str(db_path), *extra])


def _counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        return {t: int(conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]) for t in TABLES}
    finally:
        conn.close()


def test_check_prints_the_import_rejection_and_writes_nothing(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invalid = _record("Other Co (TEST)")
    del invalid["evidence"]
    path = _write(tmp_path, [_record(), invalid])
    before = _counts(db_path)
    capsys.readouterr()

    assert _run(db_path, path, "--check") == EXIT_REFUSED

    checked = capsys.readouterr()
    assert checked.out == "check: 1 valid, 1 rejected\n"
    assert _counts(db_path) == before
    rejection_lines = checked.err.splitlines()
    assert len(rejection_lines) == 1
    assert rejection_lines[0].startswith("rejected record 2")

    other_db = tmp_path / "other.db"
    db.migrate(other_db)
    assert _run(other_db, path) == EXIT_REFUSED
    imported = capsys.readouterr()
    assert [line for line in imported.err.splitlines() if line.startswith("rejected")] == (
        rejection_lines
    )


def test_all_valid_file_passes_and_creates_nothing(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, [_record(), _record("Beta Ortho (TEST)")])
    capsys.readouterr()

    assert _run(db_path, path, "--check") == EXIT_OK

    assert capsys.readouterr().out == "check: 2 valid, 0 rejected\n"
    assert _counts(db_path) == dict.fromkeys(TABLES, 0)


def test_unparseable_file_gives_the_import_error(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "broken.json"
    path.write_text("[{not json", encoding="utf-8")
    capsys.readouterr()
    assert _run(db_path, path) == EXIT_REFUSED
    import_err = capsys.readouterr().err

    assert _run(db_path, path, "--check") == EXIT_REFUSED

    check_err = capsys.readouterr().err
    assert check_err.startswith("error:")
    assert check_err == import_err


def test_check_uses_the_configured_checklist_keys(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    answered = _write(tmp_path, [_record(checklist={"direct_signal": "yes"})])
    assert _run(db_path, answered, "--check") == EXIT_OK
    other = tmp_path / "other.yaml"
    other.write_text(CONFIG_WITHOUT_SIGNAL, encoding="utf-8")
    capsys.readouterr()

    assert _run(db_path, answered, "--check", "--config", str(other)) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert "checklist.direct_signal: checklist-item" in err


def test_check_reports_a_referrer_that_is_not_a_stored_partner(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, [_record(referred_by=42)])
    capsys.readouterr()

    assert _run(db_path, path, "--check") == EXIT_REFUSED

    out = capsys.readouterr()
    assert "referred_by" in out.err
    assert out.out == "check: 0 valid, 1 rejected\n"
    assert _counts(db_path) == dict.fromkeys(TABLES, 0)


def test_check_without_a_database_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, [_record()])
    assert _run(tmp_path / "missing.db", path, "--check") == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")
