"""Tests for report: the period, its Denver date boundaries and where the output goes (R-28)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

# Denver "today" is 2026-11-30 at this instant (17:00 MST on Nov 30).
NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    return path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    code = main(
        [
            "log-inbound",
            "--db",
            str(path),
            "--channel",
            "phone",
            "--received",
            "2026-10-20 09:00",
            "--segment",
            "commercial",
            "--name",
            "Pat Lee",
        ]
    )
    assert code == EXIT_OK
    return path


def _report(db_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> str:
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), *args]) == EXIT_OK
    return capsys.readouterr().out


def _missed_call(db_path: Path, at: str) -> None:
    assert main(["log-event", "--db", str(db_path), "1", "missed_call", "--at", at]) == EXIT_OK


def _metric(text: str, label: str) -> str:
    prefix = f"- {label}: "
    matches = [line[len(prefix) :] for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {label!r} line in:\n{text}"
    return matches[0]


def test_parse_period_7d_and_30d_end_today() -> None:
    today = date(2026, 11, 30)
    assert report.parse_period("7d", None, None, today) == report.Period(date(2026, 11, 24), today)
    assert report.parse_period("30d", None, None, today) == report.Period(date(2026, 11, 1), today)


def test_parse_period_from_to_is_inclusive() -> None:
    period = report.parse_period(None, "2026-11-01", "2026-11-15", date(2026, 11, 30))
    assert period == report.Period(date(2026, 11, 1), date(2026, 11, 15))
    assert period.contains(date(2026, 11, 1))
    assert period.contains(date(2026, 11, 15))
    assert not period.contains(date(2026, 11, 16))
    assert not period.contains(date(2026, 10, 31))


def test_same_day_from_to_is_one_day() -> None:
    period = report.parse_period(None, "2026-11-15", "2026-11-15", date(2026, 11, 30))
    assert period.start == period.end == date(2026, 11, 15)


def test_period_header_7d(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = _report(db_path, capsys, "--period", "7d")
    assert "Period: 2026-11-24 to 2026-11-30 (America/Denver)" in text.splitlines()


def test_period_header_30d(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = _report(db_path, capsys, "--period", "30d")
    assert "Period: 2026-11-01 to 2026-11-30 (America/Denver)" in text.splitlines()


def test_from_to_boundaries_follow_denver_dates(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("--from", "2026-11-01", "--to", "2026-11-15")
    _missed_call(db_path, "2026-11-16T06:59:59Z")  # 23:59:59 MST on Nov 15: in
    _missed_call(db_path, "2026-11-16T07:00:00Z")  # 00:00 MST on Nov 16: out
    assert _metric(_report(db_path, capsys, *args), report.LABEL_MISSED_CALLS) == "1"
    # DST ends 2026-11-01 at 08:00Z, so Denver midnight on Nov 1 is 06:00Z (MDT).
    _missed_call(db_path, "2026-11-01T06:00:00Z")  # 00:00:00 MDT on Nov 1: in
    _missed_call(db_path, "2026-11-01T05:59:59Z")  # 23:59:59 MDT on Oct 31: out
    assert _metric(_report(db_path, capsys, *args), report.LABEL_MISSED_CALLS) == "2"


def test_start_boundary_alone(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ("--from", "2026-11-01", "--to", "2026-11-15")
    _missed_call(db_path, "2026-11-01T05:59:59Z")
    assert _metric(_report(db_path, capsys, *args), report.LABEL_MISSED_CALLS) == "0"
    _missed_call(db_path, "2026-11-01T06:00:00Z")
    assert _metric(_report(db_path, capsys, *args), report.LABEL_MISSED_CALLS) == "1"


@pytest.mark.parametrize(
    "args",
    [
        ("--period", "7d", "--from", "2026-11-01", "--to", "2026-11-15"),
        ("--period", "7d", "--from", "2026-11-01"),
        ("--period", "7d", "--to", "2026-11-15"),
        ("--from", "2026-11-01"),
        ("--to", "2026-11-15"),
        (),
        ("--from", "2026-1-5", "--to", "2026-11-15"),
        ("--from", "2026-11-01", "--to", "20261115"),
        ("--from", "2026-02-30", "--to", "2026-03-01"),
        ("--from", "2026-11-15", "--to", "2026-11-01"),
    ],
)
def test_bad_period_exits_1_and_writes_nothing(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...]
) -> None:
    out = tmp_path / "out" / "report.md"
    capsys.readouterr()
    code = main(["report", "--db", str(db_path), "--out", str(out), *args])
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert not out.exists()
    assert not out.parent.exists()


def test_stdout_report(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = _report(db_path, capsys, "--period", "7d")
    assert text.startswith("# Weekly report\n")
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert f"Generated: {timeutil.display_local(NOW)}" in text


def test_out_creates_parents_and_matches_stdout(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    expected = _report(db_path, capsys, "--period", "30d")
    out = tmp_path / "a" / "b" / "report.md"
    code = main(["report", "--db", str(db_path), "--period", "30d", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == EXIT_OK
    assert out.read_text(encoding="utf-8") == expected
    assert f"report written: {out}" in captured.out
    assert expected not in captured.out


def test_missing_database_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope.db"
    code = main(["report", "--db", str(missing), "--period", "7d"])
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert not missing.exists()


def test_unmigrated_database_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    out = tmp_path / "out" / "report.md"
    code = main(["report", "--db", str(empty), "--period", "7d", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err
    assert not out.exists()


def test_bad_config_exits_1(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["report", "--db", str(db_path), "--period", "7d", "--config", str(tmp_path / "x.yaml")]
    )
    captured = capsys.readouterr()
    assert code == EXIT_REFUSED
    assert captured.err.startswith("error:")


def test_report_does_not_write_the_database(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _missed_call(db_path, "2026-11-20T16:00:00Z")
    before = db_path.read_bytes()
    _report(db_path, capsys, "--period", "30d")
    assert db_path.read_bytes() == before
