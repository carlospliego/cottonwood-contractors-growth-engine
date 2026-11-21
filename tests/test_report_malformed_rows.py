# sir-target: tests/test_report_malformed_rows.py
"""One malformed stored row does not crash the report with a traceback (F-correctness-2)."""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from cottonwood import config, db
from cottonwood.cli import EXIT_OK, main

BASE_CONFIG = "paths:\n  backup_dir: data/backups\n"
REPORT_SOURCE = Path(__file__).resolve().parents[1] / "cottonwood" / "report.py"


def _now() -> str:
    """The real clock: the subprocess reports the 7 days ending now."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _setup(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    config_path = tmp_path / "pilot.yaml"
    config_path.write_text(BASE_CONFIG, encoding="utf-8")
    db_path = tmp_path / "cottonwood.db"
    db.migrate(db_path)
    env = {**os.environ, config.CONFIG_ENV_VAR: str(config_path), db.DB_ENV_VAR: str(db_path)}
    return db_path, env


def _execute(db_path: Path, sql: str, params: tuple[object, ...]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _lead(db_path: Path) -> None:
    args = ["--channel", "phone", "--received", "2026-11-15 08:00", "--segment", "commercial"]
    assert main(["log-inbound", "--db", str(db_path), *args, "--name", "Pat Lee"]) == EXIT_OK


def _report(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cottonwood", "report", "--period", "7d"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _stage_change(db_path: Path, payload: str, occurred_at: str) -> None:
    _execute(
        db_path,
        "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at)"
        " VALUES (1, 'stage_change', ?, 'developer', ?, ?)",
        (payload, occurred_at, occurred_at),
    )


def test_a_non_object_stage_change_payload_is_read_as_empty(tmp_path: Path) -> None:
    db_path, env = _setup(tmp_path)
    _lead(db_path)
    _stage_change(db_path, "[]", _now())
    result = _report(env)
    assert "Traceback" not in result.stderr
    assert result.returncode == 0, result.stderr


def test_an_unparseable_run_start_is_skipped(tmp_path: Path) -> None:
    db_path, env = _setup(tmp_path)
    _execute(
        db_path,
        "INSERT INTO agent_runs (skill, started_at, cost_usd, cost_estimated)"
        " VALUES ('prospect-research', 'not-a-time', '1.50', 0)",
        (),
    )
    result = _report(env)
    assert "Traceback" not in result.stderr
    assert result.returncode == 0, result.stderr


def test_an_unparseable_activity_time_is_an_error_not_a_traceback(tmp_path: Path) -> None:
    db_path, env = _setup(tmp_path)
    _lead(db_path)
    _stage_change(db_path, '{"from": "candidate", "to": "researched"}', "not-a-time")
    result = _report(env)
    assert "Traceback" not in result.stderr
    assert result.returncode == 1
    assert result.stderr.startswith("error: a stored value could not be read:")


def test_report_reads_payloads_only_through_the_guard() -> None:
    source = REPORT_SOURCE.read_text()
    guard = re.search(r"\ndef _payload\(.*?(?=\ndef )", source, re.S)
    assert guard is not None
    outside = source.replace(guard.group(0), "")
    assert "json.loads(" not in outside
    assert "json.loads(" in guard.group(0)
