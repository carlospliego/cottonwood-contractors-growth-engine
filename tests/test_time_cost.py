"""Tests for log-time and log-cost: entries, refusals, voids and totals (R-30, AC-5.x, AC-6.1)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

# Pinned after the spec's example dates; in America/Denver it is still 2026-11-30 (17:00 MST).
NOW = "2026-12-01T00:00:00Z"
DAY = "2026-11-16"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _run(db_path: Path, command: str, *args: str) -> int:
    return main([command, "--db", str(db_path), *args])


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _count(db_path: Path) -> int:
    return int(_rows(db_path, "SELECT count(*) FROM activities")[0][0])


def _last(db_path: Path) -> sqlite3.Row:
    return _rows(db_path, "SELECT * FROM activities ORDER BY id DESC LIMIT 1")[0]


def _time(db_path: Path, hours: str, *extra: str, day: str = DAY, cat: str = "outreach") -> int:
    assert _run(db_path, "log-time", hours, "--date", day, "--category", cat, *extra) == EXIT_OK
    return int(_last(db_path)["id"])


def _cost(db_path: Path, amount: str, *extra: str, day: str = DAY, cat: str = "tools") -> int:
    assert _run(db_path, "log-cost", amount, "--date", day, "--category", cat, *extra) == EXIT_OK
    return int(_last(db_path)["id"])


def _totals(db_path: Path, start: str, end: str) -> tuple[events.TimeTotals, events.CostTotals]:
    conn = db.connect(db_path)
    try:
        s, e = date.fromisoformat(start), date.fromisoformat(end)
        return events.time_totals(conn, s, e), events.cost_totals(conn, s, e)
    finally:
        conn.close()


# AC1


def test_log_time_appends_one_entry_with_defaults(db_path: Path) -> None:
    before = _count(db_path)
    assert _run(db_path, "log-time", "1.5", "--date", DAY, "--category", "Outreach") == EXIT_OK
    assert _count(db_path) == before + 1
    row = _last(db_path)
    assert row["type"] == "time_logged"
    assert row["lead_id"] is None
    assert row["occurred_at"] == "2026-11-16T07:00:00Z"
    assert json.loads(row["payload"]) == {
        "date": "2026-11-16",
        "hours": "1.5",
        "category": "outreach",
        "person": "founder",
        "estimated": False,
    }


def test_log_time_developer_estimated(db_path: Path) -> None:
    _time(db_path, "1.5", "--person", "developer", "--estimated")
    payload = json.loads(_last(db_path)["payload"])
    assert payload["person"] == "developer"
    assert payload["estimated"] is True


def test_log_time_summer_day_starts_at_six_utc(db_path: Path) -> None:
    _time(db_path, "2", day="2026-07-01")
    assert _last(db_path)["occurred_at"] == "2026-07-01T06:00:00Z"


def test_log_time_note_is_stored(db_path: Path) -> None:
    _time(db_path, "0.25", "--note", "  follow-up emails ")
    assert json.loads(_last(db_path)["payload"])["note"] == "follow-up emails"


# AC2


def test_log_cost_appends_one_entry(db_path: Path) -> None:
    before = _count(db_path)
    args = ["49.00", "--date", DAY, "--category", "Formspark plan"]
    assert _run(db_path, "log-cost", *args) == EXIT_OK
    assert _count(db_path) == before + 1
    row = _last(db_path)
    assert row["type"] == "cost_logged"
    assert row["lead_id"] is None
    assert json.loads(row["payload"]) == {
        "date": "2026-11-16",
        "amount_usd": "49.00",
        "category": "formspark plan",
        "estimated": False,
    }


def test_log_cost_estimated(db_path: Path) -> None:
    _cost(db_path, "49.00", "--estimated")
    assert json.loads(_last(db_path)["payload"])["estimated"] is True


# AC3


@pytest.mark.parametrize("hours", ["abc", "0", "-1", "24.5", "1.234", "1e1", ""])
def test_bad_hours_are_refused(
    db_path: Path, hours: str, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _count(db_path)
    code = _run(db_path, "log-time", hours, "--date", DAY, "--category", "x")
    assert code == EXIT_REFUSED
    assert "error: hours:" in capsys.readouterr().err
    assert _count(db_path) == before


@pytest.mark.parametrize("amount", ["abc", "0", "-5", "1.234", "1e1"])
def test_bad_amounts_are_refused(
    db_path: Path, amount: str, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _count(db_path)
    code = _run(db_path, "log-cost", amount, "--date", DAY, "--category", "x")
    assert code == EXIT_REFUSED
    assert "error: amount:" in capsys.readouterr().err
    assert _count(db_path) == before


def test_twenty_four_hours_is_allowed(db_path: Path) -> None:
    _time(db_path, "24")
    assert json.loads(_last(db_path)["payload"])["hours"] == "24"


@pytest.mark.parametrize("command,value", [("log-time", "1"), ("log-cost", "1.00")])
@pytest.mark.parametrize("category", ["", "   "])
def test_blank_category_is_refused(db_path: Path, command: str, value: str, category: str) -> None:
    before = _count(db_path)
    assert _run(db_path, command, value, "--date", DAY, "--category", category) == EXIT_REFUSED
    assert _count(db_path) == before


@pytest.mark.parametrize("command,value", [("log-time", "1"), ("log-cost", "1.00")])
@pytest.mark.parametrize("bad_date", ["11/16/2026", "2026-11-31", "2026-1-5", "today"])
def test_bad_date_is_refused(db_path: Path, command: str, value: str, bad_date: str) -> None:
    before = _count(db_path)
    assert _run(db_path, command, value, "--date", bad_date, "--category", "x") == EXIT_REFUSED
    assert _count(db_path) == before


@pytest.mark.parametrize("command,value", [("log-time", "1"), ("log-cost", "1.00")])
def test_date_after_denver_today_is_refused(
    db_path: Path, command: str, value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # The UTC date is already 2026-12-01; America/Denver is still on 2026-11-30.
    before = _count(db_path)
    code = _run(db_path, command, value, "--date", "2026-12-01", "--category", "x")
    assert code == EXIT_REFUSED
    assert "error: date:" in capsys.readouterr().err
    assert _count(db_path) == before
    assert _run(db_path, command, value, "--date", "2026-11-30", "--category", "x") == EXIT_OK


@pytest.mark.parametrize("command", ["log-time", "log-cost"])
@pytest.mark.parametrize("missing", ["amount", "date", "category"])
def test_entry_options_are_required_without_voids(
    db_path: Path, command: str, missing: str
) -> None:
    parts = {"amount": ["2"], "date": ["--date", DAY], "category": ["--category", "x"]}
    args = [arg for name, value in parts.items() if name != missing for arg in value]
    before = _count(db_path)
    assert _run(db_path, command, *args) == EXIT_REFUSED
    assert _count(db_path) == before


def test_blank_actor_is_refused(db_path: Path) -> None:
    before = _count(db_path)
    args = ["1", "--date", DAY, "--category", "x", "--actor", " "]
    assert _run(db_path, "log-time", *args) == EXIT_REFUSED
    assert _count(db_path) == before


# AC4


def test_voiding_a_time_entry_appends_one_correction(db_path: Path) -> None:
    entry = _time(db_path, "2")
    before = _count(db_path)
    assert _run(db_path, "log-time", "--voids", str(entry), "--note", "wrong day") == EXIT_OK
    assert _count(db_path) == before + 1
    row = _last(db_path)
    assert row["type"] == "correction"
    assert row["lead_id"] is None
    assert row["voids_activity_id"] == entry
    assert json.loads(row["payload"]) == {"note": "wrong day"}


def test_voiding_a_cost_entry_appends_one_correction(db_path: Path) -> None:
    entry = _cost(db_path, "10.00")
    before = _count(db_path)
    assert _run(db_path, "log-cost", "--voids", str(entry)) == EXIT_OK
    assert _count(db_path) == before + 1
    row = _last(db_path)
    assert row["type"] == "correction"
    assert row["lead_id"] is None
    assert row["voids_activity_id"] == entry


def test_void_refusals_write_nothing(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    time_id = _time(db_path, "2")
    cost_id = _cost(db_path, "10.00")
    assert _run(db_path, "log-time", "--voids", str(time_id)) == EXIT_OK
    capsys.readouterr()
    cases = [
        ("log-time", "--voids", str(cost_id)),  # wrong kind
        ("log-cost", "--voids", str(time_id)),  # wrong kind
        ("log-time", "--voids", "9999"),  # missing id
        ("log-time", "--voids", str(time_id)),  # already void
        ("log-cost", "--voids", str(cost_id), "5"),  # with an amount
        ("log-cost", "--voids", str(cost_id), "--date", DAY),
        ("log-cost", "--voids", str(cost_id), "--category", "x"),
        ("log-time", "--voids", str(time_id), "--person", "founder"),
        ("log-cost", "--voids", str(cost_id), "--estimated"),
    ]
    for command, *args in cases:
        before = _count(db_path)
        assert _run(db_path, command, *args) == EXIT_REFUSED, args
        assert capsys.readouterr().err.startswith("error:"), args
        assert _count(db_path) == before, args


def test_void_entry_refuses_a_lead_event(db_path: Path) -> None:
    code = main(
        [
            "log-inbound",
            "--db",
            str(db_path),
            "--channel",
            "form",
            "--received",
            "2026-11-15 08:00",
            "--segment",
            "commercial",
            "--name",
            "Pat Lee",
        ]
    )
    assert code == EXIT_OK
    assert main(["log-event", "--db", str(db_path), "1", "call", "--at", f"{DAY} 09:00"]) == 0
    call_id = int(_last(db_path)["id"])
    before = _count(db_path)
    assert _run(db_path, "log-time", "--voids", str(call_id)) == EXIT_REFUSED
    assert _count(db_path) == before


# AC5


def test_totals_split_and_exclude_void_and_out_of_range(db_path: Path) -> None:
    _time(db_path, "1.5", day="2026-11-16")
    _time(db_path, "0.25", "--person", "developer", day="2026-11-17")
    _time(db_path, "2", "--estimated", day="2026-11-20")
    voided = _time(db_path, "7", day="2026-11-18")
    assert _run(db_path, "log-time", "--voids", str(voided)) == EXIT_OK
    _time(db_path, "3", day="2026-11-15")  # before the range
    _time(db_path, "4", day="2026-11-21")  # after the range
    _cost(db_path, "49.00", cat="formspark plan", day="2026-11-16")
    _cost(db_path, "0.10", cat="domain", day="2026-11-20")
    _cost(db_path, "0.20", "--estimated", cat="domain", day="2026-11-19")
    void_cost = _cost(db_path, "100.00", cat="ads", day="2026-11-17")
    assert _run(db_path, "log-cost", "--voids", str(void_cost)) == EXIT_OK
    _cost(db_path, "5.00", cat="ads", day="2026-11-22")  # after the range

    times, costs = _totals(db_path, "2026-11-16", "2026-11-20")

    assert times.total == Decimal("3.75")
    assert times.by_person == {"founder": Decimal("3.5"), "developer": Decimal("0.25")}
    assert times.observed == Decimal("1.75")
    assert times.estimated == Decimal("2")
    assert costs.total == Decimal("49.30")
    assert costs.by_category == {"formspark plan": Decimal("49.00"), "domain": Decimal("0.30")}
    assert costs.observed == Decimal("49.10")
    assert costs.estimated == Decimal("0.20")
    assert isinstance(costs.total, Decimal)


def test_totals_are_exact_decimals(db_path: Path) -> None:
    for _ in range(3):
        _cost(db_path, "0.10")
    _, costs = _totals(db_path, DAY, DAY)
    assert costs.total == Decimal("0.30")
    assert str(costs.total) == "0.30"


def test_totals_range_is_inclusive_on_both_ends(db_path: Path) -> None:
    _time(db_path, "1", day="2026-11-16")
    _time(db_path, "2", day="2026-11-17")
    times, _ = _totals(db_path, "2026-11-16", "2026-11-17")
    assert times.total == Decimal("3")
    times, _ = _totals(db_path, "2026-11-17", "2026-11-17")
    assert times.total == Decimal("2")


def test_totals_are_zero_for_an_empty_range(db_path: Path) -> None:
    _time(db_path, "1", day="2026-11-16")
    _cost(db_path, "1.00", day="2026-11-16")
    times, costs = _totals(db_path, "2026-11-01", "2026-11-10")
    assert times == events.TimeTotals(Decimal(0), {}, Decimal(0), Decimal(0))
    assert costs == events.CostTotals(Decimal(0), {}, Decimal(0), Decimal(0))


# AC6


@pytest.mark.parametrize(
    "args",
    [
        ["log-time", "1", "--date", DAY, "--category", "x"],
        ["log-cost", "1.00", "--date", DAY, "--category", "x"],
        ["log-time", "--voids", "1"],
        ["log-cost", "--voids", "1"],
    ],
)
def test_missing_database_is_refused(
    tmp_path: Path, args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.db"
    assert main([*args, "--db", str(missing)]) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert not missing.exists()


@pytest.mark.parametrize(
    "args",
    [
        ["log-time", "1", "--date", DAY, "--category", "x"],
        ["log-cost", "1.00", "--date", DAY, "--category", "x"],
        ["log-time", "--voids", "1"],
        ["log-cost", "--voids", "1"],
    ],
)
def test_unmigrated_database_is_refused(
    tmp_path: Path, args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    assert main([*args, "--db", str(empty)]) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    conn = sqlite3.connect(empty)
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()
    assert tables == []
