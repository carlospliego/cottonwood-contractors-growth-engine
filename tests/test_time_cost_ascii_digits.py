# sir-target: tests/test_time_cost_ascii_digits.py
"""Hours, amounts and entry dates accept ASCII digits only (F-correctness-5)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
ARABIC_INDIC_DATE = "٢٠٢٦-١١-١٦"  # 2026-11-16 in Arabic-Indic digits


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
    finally:
        conn.close()


def _run(db_path: Path, *args: str) -> int:
    return main([args[0], "--db", str(db_path), *args[1:]])


@pytest.mark.parametrize(
    ("args", "field"),
    [
        (("log-time", "١.٥", "--date", "2026-11-16", "--category", "outreach"), "hours"),
        (("log-cost", "12.50", "--date", ARABIC_INDIC_DATE, "--category", "tools"), "date"),
        (("log-cost", "１２", "--date", "2026-11-16", "--category", "tools"), "amount"),
        (("log-time", "2", "--date", "２０２６-１１-１６", "--category", "outreach"), "date"),
    ],
    ids=["arabic-indic-hours", "arabic-indic-date", "fullwidth-amount", "fullwidth-date"],
)
def test_non_ascii_digits_exit_1_and_write_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...], field: str
) -> None:
    assert _run(db_path, *args) == EXIT_REFUSED
    assert f"error: {field}:" in capsys.readouterr().err
    assert _count(db_path) == 0


def test_the_same_values_in_ascii_digits_are_saved(db_path: Path) -> None:
    assert _run(db_path, "log-time", "1.5", "--date", "2026-11-16", "--category", "x") == EXIT_OK
    assert _run(db_path, "log-cost", "12.50", "--date", "2026-11-16", "--category", "y") == 0
    assert _count(db_path) == 2
