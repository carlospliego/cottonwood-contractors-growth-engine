"""Tests for record-run: one agent_runs row per Claude skill run, cost source named (R-26)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, runs, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, EXIT_USAGE, main

NOW = "2026-12-01T00:00:00Z"  # Denver: 2026-11-30 17:00
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


def _args(db_path: Path, *flags: str, **changes: str) -> list[str]:
    values = dict(BASE)
    for key, value in changes.items():
        values["--" + key.replace("_", "-")] = value
    argv = ["record-run"]
    for option, value in values.items():
        argv += [option, value]
    return [*argv, *flags, "--db", str(db_path)]


def _record(db_path: Path, *flags: str, **changes: str) -> int:
    return main(_args(db_path, *flags, **changes))


def _rows(db_path: Path) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute("SELECT * FROM agent_runs ORDER BY id"))
    finally:
        conn.close()


# --- AC 1: stored row and printed line ----------------------------------------------------


def test_run_is_stored_with_every_field(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _record(db_path) == EXIT_OK

    assert capsys.readouterr().out == (
        "run 1 recorded: research-prospects 1.0.0, 3.25 USD (claude-code-cost)\n"
    )
    (row,) = _rows(db_path)
    assert dict(row) == {
        "id": 1,
        "skill": "research-prospects",
        "skill_version": "1.0.0",
        "model": "claude-opus-5-5",
        "started_at": "2026-11-30T16:00:00Z",
        "ended_at": "2026-11-30T16:40:00Z",
        "input_ref": "brief: GC firms in Salt Lake County",
        "output_ref": "out/research/2026-11-30-gc.json",
        "validation": "passed",
        "tokens": 120000,
        "cost_usd": "3.25",
        "cost_source": "claude-code-cost",
        "cost_estimated": 0,
    }


def test_utc_times_are_accepted(db_path: Path) -> None:
    assert _record(db_path, started="2026-11-30T16:00:00Z", ended="2026-11-30T16:40:00Z") == EXIT_OK
    (row,) = _rows(db_path)
    assert (row["started_at"], row["ended_at"]) == ("2026-11-30T16:00:00Z", "2026-11-30T16:40:00Z")


# --- AC 2: estimated, billing console, report ---------------------------------------------


def test_estimated_cost_is_marked(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _record(db_path, "--estimated") == EXIT_OK
    assert capsys.readouterr().out.rstrip().endswith("(claude-code-cost, estimated)")
    assert _rows(db_path)[0]["cost_estimated"] == 1


def test_billing_console_source_is_stored(db_path: Path) -> None:
    assert _record(db_path, cost_source="billing-console") == EXIT_OK
    assert _rows(db_path)[0]["cost_source"] == "billing-console"


def test_recorded_runs_feed_the_report(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _record(db_path) == EXIT_OK
    assert _record(db_path, "--estimated", cost="1.1") == EXIT_OK
    capsys.readouterr()

    assert main(["report", "--from", "2026-11-30", "--to", "2026-11-30", "--db", str(db_path)]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert "- Model cost: 4.35" in lines
    assert "- Model cost observed: 3.25" in lines
    assert "- Model cost estimated: 1.10" in lines


def test_small_costs_keep_four_places(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _record(db_path, cost="0.0375") == EXIT_OK
    assert _rows(db_path)[0]["cost_usd"] == "0.0375"
    assert "0.0375 USD" in capsys.readouterr().out


# --- AC 3: refusals ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "changes"),
    [
        ("skill", {"skill": "  "}),
        ("skill-version", {"skill_version": "  "}),
        ("model", {"model": "  "}),
        ("input", {"input": "  "}),
        ("output", {"output": "  "}),
        ("started", {"started": "yesterday"}),
        ("ended", {"ended": "2026-11-30 25:00"}),
        ("ended", {"ended": "2026-11-30 08:59"}),
        ("started", {"started": "2026-12-01 00:00", "ended": "2026-12-01 01:00"}),
        ("tokens", {"tokens": "-1"}),
        ("tokens", {"tokens": "1.5"}),
        ("cost", {"cost": "-1"}),
        ("cost", {"cost": "1e3"}),
        ("cost", {"cost": "1.23456"}),
    ],
)
def test_bad_fields_are_refused(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    field: str,
    changes: dict[str, str],
) -> None:
    capsys.readouterr()
    assert _record(db_path, **changes) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith(f"error: {field}:")
    assert _rows(db_path) == []


@pytest.mark.parametrize("changes", [{"validation": "maybe"}, {"cost_source": "guess"}])
def test_choices_are_usage_errors(db_path: Path, changes: dict[str, str]) -> None:
    assert _record(db_path, **changes) == EXIT_USAGE
    assert _rows(db_path) == []


def test_missing_database_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope" / "cottonwood.db"
    assert _record(missing) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error:")


# --- module ------------------------------------------------------------------------------


def test_parse_cost_normalizes_nothing_but_whitespace() -> None:
    assert runs.parse_cost(" 3.25 ") == "3.25"
    assert runs.parse_cost("0") == "0"
    with pytest.raises(runs.RunError):
        runs.parse_cost("+3")
    with pytest.raises(runs.RunError):
        runs.parse_cost("3.")
