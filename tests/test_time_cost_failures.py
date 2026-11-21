# sir-target: tests/test_time_cost_failures.py
"""log-time / log-cost: a failed write and a blank actor are refused cleanly (F-testing-2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

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


def _count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
    finally:
        conn.close()


def _last_id(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT max(id) FROM activities").fetchone()[0])
    finally:
        conn.close()


def _fail_every_insert(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TRIGGER forced_failure BEFORE INSERT ON activities"
            " BEGIN SELECT RAISE(ABORT, 'forced insert failure'); END"
        )
        conn.commit()
    finally:
        conn.close()


def _entry(db_path: Path, command: str) -> int:
    assert _run(db_path, command, "2", "--date", DAY, "--category", "outreach") == EXIT_OK
    return _last_id(db_path)


# (command, arguments) for a new entry; the --voids forms are built from a logged entry.
NEW_ENTRIES = [
    ("log-time", ("2", "--date", DAY, "--category", "outreach")),
    ("log-cost", ("12.50", "--date", DAY, "--category", "tools")),
]


@pytest.mark.parametrize(("command", "args"), NEW_ENTRIES, ids=["log-time", "log-cost"])
def test_insert_failure_on_a_new_entry_is_a_clean_refusal(
    db_path: Path, capsys: pytest.CaptureFixture[str], command: str, args: tuple[str, ...]
) -> None:
    _fail_every_insert(db_path)
    before = _count(db_path)
    capsys.readouterr()

    assert _run(db_path, command, *args) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: could not save the entry")
    assert "Traceback" not in err
    assert _count(db_path) == before


@pytest.mark.parametrize("command", ["log-time", "log-cost"])
def test_insert_failure_on_a_void_is_a_clean_refusal(
    db_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    target = _entry(db_path, command)
    _fail_every_insert(db_path)
    before = _count(db_path)
    capsys.readouterr()

    assert _run(db_path, command, "--voids", str(target), "--note", "wrong day") == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: could not save the entry")
    assert "Traceback" not in err
    assert _count(db_path) == before


def test_log_cost_with_a_blank_actor_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _count(db_path)
    args = ("12.50", "--date", DAY, "--category", "tools", "--actor", " ")
    assert _run(db_path, "log-cost", *args) == EXIT_REFUSED
    assert "actor" in capsys.readouterr().err
    assert _count(db_path) == before


@pytest.mark.parametrize("command", ["log-time", "log-cost"])
def test_void_with_a_blank_actor_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    target = _entry(db_path, command)
    before = _count(db_path)
    capsys.readouterr()

    assert _run(db_path, command, "--voids", str(target), "--actor", " ") == EXIT_REFUSED

    assert "actor" in capsys.readouterr().err
    assert _count(db_path) == before
