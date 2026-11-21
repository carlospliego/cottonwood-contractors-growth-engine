# sir-target: tests/test_entry_confirmation_lines.py
"""The exact stdout line log-time and log-cost print for an entry and a void (F-testing-3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _out(capsys: pytest.CaptureFixture[str], db_path: Path, *args: str) -> str:
    command, *rest = args
    assert main([command, "--db", str(db_path), *rest]) == EXIT_OK
    return capsys.readouterr().out


def test_time_entry_line(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = _out(
        capsys, db_path, "log-time", "1.5", "--date", "2026-11-16", "--category", "Outreach",
        "--person", "developer",
    )  # fmt: skip
    assert out == "logged time_logged activity 1: 1.5 h outreach (developer) on 2026-11-16\n"


def test_time_entry_line_names_the_default_person(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _out(capsys, db_path, "log-time", "2", "--date", "2026-11-17", "--category", "calls")
    assert out == "logged time_logged activity 1: 2 h calls (founder) on 2026-11-17\n"


def test_cost_entry_line(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = _out(capsys, db_path, "log-cost", "49.00", "--date", "2026-11-16", "--category", "Tools")
    assert out == "logged cost_logged activity 1: $49.00 tools on 2026-11-16\n"


def test_void_lines(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _out(capsys, db_path, "log-time", "1", "--date", "2026-11-16", "--category", "calls")
    # The second entry's line carries its own id, not a fixed 1.
    assert _out(
        capsys, db_path, "log-cost", "5.00", "--date", "2026-11-16", "--category", "tools"
    ) == ("logged cost_logged activity 2: $5.00 tools on 2026-11-16\n")
    assert _out(capsys, db_path, "log-time", "--voids", "1") == (
        "logged correction activity 3; voids time_logged activity 1\n"
    )
    assert _out(capsys, db_path, "log-cost", "--voids", "2") == (
        "logged correction activity 4; voids cost_logged activity 2\n"
    )
