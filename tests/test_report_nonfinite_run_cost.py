# sir-target: tests/test_report_nonfinite_run_cost.py
"""A non-finite agent_runs.cost_usd ('NaN', 'Infinity') is skipped, not summed (F-testing-2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
PERIOD = ("--from", "2026-11-10", "--to", "2026-11-20")
IN_PERIOD = "2026-11-15T17:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(config_path))
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _runs(db_path: Path, costs: list[str]) -> None:
    conn = db.connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO agent_runs (skill, started_at, cost_usd, cost_estimated)"
            " VALUES ('prospect-research', ?, ?, 0)",
            [(IN_PERIOD, cost) for cost in costs],
        )
        conn.commit()
    finally:
        conn.close()


def _metric(text: str, label: str) -> str:
    prefix = f"- {label}: "
    matches = [line[len(prefix) :] for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {label!r} line in:\n{text}"
    return matches[0]


@pytest.mark.parametrize("bad", [["NaN", "Infinity"], ["-Infinity"], ["nan", "inf"]])
def test_non_finite_run_costs_are_skipped(
    db_path: Path, capsys: pytest.CaptureFixture[str], bad: list[str]
) -> None:
    _runs(db_path, [*bad, "1.00"])
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), *PERIOD]) == EXIT_OK
    text = capsys.readouterr().out
    assert _metric(text, report.LABEL_MODEL_COST) == "1.00"
    assert _metric(text, report.LABEL_MODEL_OBSERVED) == "1.00"
