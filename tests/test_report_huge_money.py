# sir-target: tests/test_report_huge_money.py
"""A huge cost cap or run cost prints instead of an InvalidOperation traceback (F-correctness-1)."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cottonwood import config, db
from cottonwood.report import money

BIG = "1000000000000000000000000000000"  # 10**30: 33 digits at 2 places, over the default 28
BASE_CONFIG = "paths:\n  backup_dir: data/backups\n"


def _report(
    tmp_path: Path, config_text: str, run_cost: str | None
) -> subprocess.CompletedProcess[str]:
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    db_path = tmp_path / "cottonwood.db"
    db.migrate(db_path)
    if run_cost is not None:
        conn = db.connect(db_path)
        try:
            # The real clock: the subprocess reports the 7 days ending now.
            started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                "INSERT INTO agent_runs (skill, started_at, cost_usd, cost_estimated)"
                " VALUES ('prospect-research', ?, ?, 0)",
                (started, run_cost),
            )
            conn.commit()
        finally:
            conn.close()
    env = {**os.environ, config.CONFIG_ENV_VAR: str(config_path), db.DB_ENV_VAR: str(db_path)}
    return subprocess.run(
        [sys.executable, "-m", "cottonwood", "report", "--period", "7d"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_a_huge_cap_prints(tmp_path: Path) -> None:
    config_text = BASE_CONFIG + f'report:\n  model_cost_cap_usd: "{BIG}"\n'
    result = _report(tmp_path, config_text, None)
    assert "Traceback" not in result.stderr
    assert result.returncode == 0, result.stderr
    assert f"of {BIG}.00" in result.stdout


def test_a_huge_run_cost_prints(tmp_path: Path) -> None:
    result = _report(tmp_path, BASE_CONFIG, "1E+30")
    assert "Traceback" not in result.stderr
    assert result.returncode == 0, result.stderr
    assert f"{BIG}.00" in result.stdout


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("1E+30", f"{BIG}.00"),
        ("123456789012345678901234567.891", "123456789012345678901234567.89"),
        ("1.755", "1.76"),
        ("0", "0.00"),
        ("-2.5", "-2.50"),
    ],
)
def test_money_rounds_any_finite_amount(value: str, shown: str) -> None:
    assert money(Decimal(value)) == shown
