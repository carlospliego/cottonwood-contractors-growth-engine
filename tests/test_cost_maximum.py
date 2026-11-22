# sir-target: tests/test_cost_maximum.py
"""Cost entries are bounded by MAX_COST_USD, so cost totals stay exact (F-correctness-6)."""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
DAY = "2026-11-16"
THIRTY_DIGITS = "123456789012345678901234567890"


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


def _cost(db_path: Path, amount: str) -> int:
    return main(["log-cost", "--db", str(db_path), amount, "--date", DAY, "--category", "tools"])


def test_the_maximum_is_documented_in_the_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["log-cost", "--help"]) == EXIT_OK
    help_text = " ".join(capsys.readouterr().out.split())
    assert f"at most {events.MAX_COST_USD} per entry" in help_text


@pytest.mark.parametrize("amount", ["1000000.01", "1000001", THIRTY_DIGITS])
def test_an_amount_above_the_maximum_exits_1_and_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str], amount: str
) -> None:
    assert _cost(db_path, amount) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error: amount: at most 1000000")
    assert _count(db_path) == 0


def test_the_maximum_itself_is_saved(db_path: Path) -> None:
    assert _cost(db_path, "1000000.00") == EXIT_OK
    assert _count(db_path) == 1


def test_totals_of_maximum_entries_are_exact(db_path: Path) -> None:
    for amount in ("1000000.00", "999999.99", "0.01"):
        assert _cost(db_path, amount) == EXIT_OK
    conn = db.connect(db_path)
    try:
        totals = events.cost_totals(conn, date(2026, 11, 1), date(2026, 11, 30))
    finally:
        conn.close()
    assert totals.total == Decimal("2000000.00")
