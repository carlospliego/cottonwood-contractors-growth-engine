# sir-target: tests/test_record_run_optional_cost.py
"""record-run without tokens or cost: stored as unknown (NULL), never as 0 (R-26, CCGE-152).

On a subscription plan Claude Code's /cost may show no dollar figure, so --tokens, --cost and
--cost-source can be left out. --cost-source and --estimated describe a cost and need --cost.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_USAGE, main

NOW = "2026-12-01T00:00:00Z"  # Denver: 2026-11-30 17:00
REQUIRED = [
    "--skill",
    "research-prospects",
    "--skill-version",
    "1.3.0",
    "--model",
    "claude-opus-5-5",
    "--started",
    "2026-11-30 09:00",
    "--ended",
    "2026-11-30 09:40",
    "--input",
    "brief: demand",
    "--output",
    "out/research/2026-11-30-demand.json",
    "--validation",
    "passed",
]


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


def _record(db_path: Path, *flags: str) -> int:
    return main(["record-run", *REQUIRED, *flags, "--db", str(db_path)])


def _rows(db_path: Path) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute("SELECT * FROM agent_runs ORDER BY id"))
    finally:
        conn.close()


# --- AC 1: no tokens and no cost --------------------------------------------------------


def test_run_without_tokens_or_cost_is_stored_as_unknown(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _record(db_path) == EXIT_OK

    rows = _rows(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["tokens"] is None
    assert row["cost_usd"] is None
    assert row["cost_source"] is None
    assert row["cost_estimated"] is None
    out = capsys.readouterr().out
    assert "cost not recorded" in out
    assert "tokens not recorded" in out


# --- AC 2: tokens but no cost ------------------------------------------------------------


def test_tokens_without_cost(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _record(db_path, "--tokens", "127190") == EXIT_OK

    row = _rows(db_path)[0]
    assert row["tokens"] == 127190
    assert row["cost_usd"] is None
    assert row["cost_source"] is None
    assert row["cost_estimated"] is None
    out = capsys.readouterr().out
    assert "cost not recorded" in out
    assert "tokens not recorded" not in out


# --- AC 3: cost flags need each other ----------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "named"),
    [
        (["--cost-source", "claude-code-cost"], "--cost-source"),
        (["--estimated"], "--estimated"),
        (["--cost", "2.50"], "--cost"),
        (["--tokens", "100", "--cost-source", "billing-console", "--estimated"], "--cost-source"),
    ],
)
def test_cost_flags_without_each_other_are_usage_errors(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    flags: list[str],
    named: str,
) -> None:
    capsys.readouterr()
    assert _record(db_path, *flags) == EXIT_USAGE
    err = capsys.readouterr().err
    assert err.startswith(f"error: {named} ")
    assert _rows(db_path) == []


# --- AC 4: the report counts a run with no cost in neither total ---------------------------


def test_report_skips_a_run_with_no_cost(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _record(db_path) == EXIT_OK
    assert _record(db_path, "--cost", "2.50", "--cost-source", "claude-code-cost") == EXIT_OK
    capsys.readouterr()

    assert main(["report", "--from", "2026-11-30", "--to", "2026-11-30", "--db", str(db_path)]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert "- Model cost observed: 2.50" in lines
    assert "- Model cost estimated: 0.00" in lines
