"""record-run refuses a run whose --ended time is later than now (CCGE-115)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # Denver: 2026-11-30 17:00


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


def _record(db_path: Path, started: str, ended: str) -> int:
    return main(
        [
            "record-run",
            "--skill", "research-prospects",
            "--skill-version", "1.0.0",
            "--model", "claude-opus-5-5",
            "--started", started,
            "--ended", ended,
            "--input", "brief: test",
            "--output", "out/research/test.json",
            "--validation", "passed",
            "--tokens", "100",
            "--cost", "0.10",
            "--cost-source", "claude-code-cost",
            "--db", str(db_path),
        ]
    )  # fmt: skip


def _run_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("SELECT count(*) FROM agent_runs").fetchone()[0])


def test_ended_later_than_now_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _record(db_path, "2026-11-30 09:00", "2026-12-01 01:00") == EXIT_REFUSED
    err = capsys.readouterr().err
    assert any(line.startswith("error: ended:") for line in err.splitlines())
    assert _run_count(db_path) == 0


def test_ended_equal_to_now_is_accepted(db_path: Path) -> None:
    assert _record(db_path, "2026-11-30 09:00", "2026-11-30 17:00") == EXIT_OK
    assert _run_count(db_path) == 1
