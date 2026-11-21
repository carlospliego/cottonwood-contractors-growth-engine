# sir-target: tests/test_gate_commands_database_errors.py
"""A database error in approve, claims or suppress is one error line and exit 1 (R-18/19/24).

F-testing-3: each handler catches sqlite3.Error and prints 'error: could not ...', but no test
reached those branches, so dropping one would only show as a traceback in the founder's terminal.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import claims, config, db, gate, timeutil
from cottonwood.cli import EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
FAILURE = "database is locked"


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


@pytest.fixture
def library(tmp_path: Path) -> Path:
    path = tmp_path / "claims.yaml"
    path.write_text(
        "claims:\n"
        "  - id: service-area\n"
        "    text: Serves the Salt Lake valley.\n"
        "    status: unverified\n"
        "    evidence: Founder email.\n",
        encoding="utf-8",
    )
    return path


def _raise(*_args: object, **_kwargs: object) -> None:
    raise sqlite3.OperationalError(FAILURE)


def _activity_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
    finally:
        conn.close()


def _refused(capsys: pytest.CaptureFixture[str], command: list[str]) -> list[str]:
    capsys.readouterr()
    assert main(command) == EXIT_REFUSED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Traceback" not in captured.err
    return captured.err.splitlines()


def test_approve_reports_a_database_error_on_one_line(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "approve", _raise)
    command = ["approve", "offer", "spring-tune-up", "--approver", "Founder", "--reference", "r"]
    lines = _refused(capsys, [*command, "--db", str(db_path)])
    assert lines == [f"error: could not record the approval: {FAILURE}"]
    assert _activity_count(db_path) == 0


def test_claims_reports_a_database_error_on_one_line(
    db_path: Path,
    library: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(claims, "effective_statuses", _raise)
    lines = _refused(capsys, ["claims", "--claims", str(library), "--db", str(db_path)])
    assert lines == [f"error: could not read the claim approvals: {FAILURE}"]


def test_suppress_reports_a_database_error_on_one_line(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "suppress", _raise)
    command = ["suppress", "jo@example.com", "--reason", "asked", "--db", str(db_path)]
    lines = _refused(capsys, command)
    assert lines == [f"error: could not record the suppression: {FAILURE}"]
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM suppression").fetchone()[0] == 0
    finally:
        conn.close()
