# sir-target: tests/test_correction_refusals.py
"""log-event correction refusals: each exits 1 and writes nothing (F-testing-1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"  # 2026-11-30 17:00 in America/Denver


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Lead 1 (inbound) with one call, activity CALL_ID, to void."""
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    args = ["--channel", "form", "--received", "2026-11-15 08:00", "--segment", "commercial"]
    assert main(["log-inbound", "--db", str(path), *args, "--name", "Pat Lee"]) == EXIT_OK
    assert main(["log-event", "--db", str(path), "1", "call", "--at", "2026-11-16 09:30"]) == 0
    return path


def _call_id(db_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    try:
        return str(conn.execute("SELECT max(id) FROM activities WHERE type = 'call'").fetchone()[0])
    finally:
        conn.close()


def _snapshot(db_path: Path) -> tuple[int, str]:
    conn = sqlite3.connect(db_path)
    try:
        count = int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
        stage = str(conn.execute("SELECT stage FROM leads WHERE id = 1").fetchone()[0])
    finally:
        conn.close()
    return count, stage


def _correction(path: Path, *args: str) -> int:
    return main(["log-event", "--db", str(path), "1", "correction", *args])


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        (("--at", "yesterday-ish"), "at"),
        (("--at", "2026-11-30 17:01"), "at"),  # one minute after the pinned now
        (("--at", "2026-11-16 10:00", "--actor", "  "), "actor"),
        (("--at", "2026-11-16 10:00", "--procurement-url", "https://example.com/rfp"), "url"),
    ],
    ids=["unparseable-at", "future-at", "blank-actor", "procurement-url"],
)
def test_bad_input_exits_1_and_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str], extra: tuple[str, ...], field: str
) -> None:
    before = _snapshot(db_path)
    capsys.readouterr()

    assert _correction(db_path, "--voids", _call_id(db_path), *extra) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert field in err
    assert "Traceback" not in err
    assert _snapshot(db_path) == before


def test_future_at_names_now(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    code = _correction(db_path, "--voids", _call_id(db_path), "--at", "2026-12-25 09:00")
    assert code == EXIT_REFUSED
    assert "is later than now" in capsys.readouterr().err


def test_the_same_correction_at_a_past_time_is_saved(db_path: Path) -> None:
    """Control: the refusals above come from the bad value, not the setup."""
    count, _ = _snapshot(db_path)
    assert _correction(db_path, "--voids", _call_id(db_path), "--at", "2026-11-16 10:00") == 0
    assert _snapshot(db_path)[0] == count + 1


def test_missing_database_exits_1_and_creates_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.db"
    assert _correction(missing, "--voids", "2", "--at", "2026-11-16 10:00") == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert not missing.exists()


def test_unmigrated_database_exits_1_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()  # a database file with no schema (user_version 0)
    before = empty.read_bytes()

    assert _correction(empty, "--voids", "2", "--at", "2026-11-16 10:00") == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert empty.read_bytes() == before
