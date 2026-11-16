# sir-target: tests/test_record_run_tokens_limit.py
"""record-run refuses a token count beyond SQLite's INTEGER range instead of crashing."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
BASE = {
    "--skill": "research-prospects",
    "--skill-version": "1.0.0",
    "--model": "claude-opus-5-5",
    "--started": "2026-11-30 09:00",
    "--ended": "2026-11-30 09:40",
    "--input": "brief: GC firms in Salt Lake County",
    "--output": "out/research/2026-11-30-gc.json",
    "--validation": "passed",
    "--tokens": "120000",
    "--cost": "3.25",
    "--cost-source": "claude-code-cost",
}


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


def _record(db_path: Path, tokens: str) -> int:
    values = dict(BASE)
    values["--tokens"] = tokens
    argv = ["record-run"]
    for option, value in values.items():
        argv += [option, value]
    return main([*argv, "--db", str(db_path)])


def _row_count(db_path: Path) -> int:
    conn = db.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
    finally:
        conn.close()


def test_tokens_beyond_sqlite_integer_are_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert _record(db_path, "99999999999999999999") == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: tokens:")
    assert _row_count(db_path) == 0


def test_tokens_at_sqlite_maximum_are_stored(db_path: Path) -> None:
    assert _record(db_path, "9223372036854775807") == 0
    assert _row_count(db_path) == 1
