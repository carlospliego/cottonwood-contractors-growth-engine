"""Tests for report's inbound section: inquiries, the acknowledgement target, calls (R-28, R-3)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_OK, main

# Denver "today" is Monday 2026-11-30 at this instant; --period 30d is 2026-11-01..11-30.
NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _inquiry(
    db_path: Path,
    received: str,
    *,
    channel: str = "form",
    segment: str = "commercial",
    test: bool = False,
) -> int:
    args = [
        "log-inbound",
        "--db",
        str(db_path),
        "--channel",
        channel,
        "--received",
        received,
        "--segment",
        segment,
        "--name",
        "Pat Lee",
        "--confirm-duplicate",
    ]
    if test:
        args.append("--test")
    assert main(args) == EXIT_OK
    conn = db.connect(db_path)
    try:
        return int(conn.execute("SELECT max(id) FROM leads").fetchone()[0])
    finally:
        conn.close()


def _event(db_path: Path, lead_id: int, kind: str, at: str) -> int:
    assert main(["log-event", "--db", str(db_path), str(lead_id), kind, "--at", at]) == EXIT_OK
    conn = db.connect(db_path)
    try:
        return int(conn.execute("SELECT max(id) FROM activities").fetchone()[0])
    finally:
        conn.close()


def _void(db_path: Path, lead_id: int, activity_id: int) -> None:
    code = main(
        [
            "log-event",
            "--db",
            str(db_path),
            str(lead_id),
            "correction",
            "--voids",
            str(activity_id),
            "--at",
            "2026-11-30 12:00",
        ]
    )
    assert code == EXIT_OK


def _report(db_path: Path, capsys: pytest.CaptureFixture[str], period: str = "30d") -> str:
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), "--period", period]) == EXIT_OK
    return capsys.readouterr().out


def _metric(text: str, label: str) -> str:
    prefix = f"- {label}: "
    matches = [line[len(prefix) :] for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {label!r} line in:\n{text}"
    return matches[0]


def _ack_counts(text: str) -> tuple[str, str, str]:
    return (
        _metric(text, report.LABEL_ACK_WITHIN),
        _metric(text, report.LABEL_ACK_OUTSIDE),
        _metric(text, report.LABEL_NOT_ACKNOWLEDGED),
    )


ALL_INBOUND_LABELS = (
    report.LABEL_INQUIRIES,
    f"{report.LABEL_CHANNEL} form",
    f"{report.LABEL_CHANNEL} phone",
    f"{report.LABEL_SEGMENT} commercial",
    f"{report.LABEL_SEGMENT} residential",
    f"{report.LABEL_SEGMENT} unknown",
    report.LABEL_ACK_WITHIN,
    report.LABEL_ACK_OUTSIDE,
    report.LABEL_NOT_ACKNOWLEDGED,
    report.LABEL_MISSED_CALLS,
    report.LABEL_RETURNED_CALLS,
)


def test_empty_database_prints_every_inbound_line_as_zero(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = _report(db_path, capsys)
    assert "## Inbound" in text
    for label in ALL_INBOUND_LABELS:
        assert _metric(text, label) == "0"


def test_inquiries_by_channel_and_segment(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _inquiry(db_path, "2026-11-20 09:00", channel="form", segment="commercial")
    _inquiry(db_path, "2026-11-21 09:00", channel="phone", segment="residential")
    _inquiry(db_path, "2026-11-22 09:00", channel="phone", segment="unknown")
    _inquiry(db_path, "2026-11-23 09:00", channel="form", segment="commercial", test=True)
    _inquiry(db_path, "2026-10-31 23:59", channel="form", segment="commercial")  # before 11-01
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_INQUIRIES) == "3"
    assert _metric(text, f"{report.LABEL_CHANNEL} form") == "1"
    assert _metric(text, f"{report.LABEL_CHANNEL} phone") == "2"
    assert _metric(text, f"{report.LABEL_SEGMENT} commercial") == "1"
    assert _metric(text, f"{report.LABEL_SEGMENT} residential") == "1"
    assert _metric(text, f"{report.LABEL_SEGMENT} unknown") == "1"


def test_inquiry_received_on_period_start_counts(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _inquiry(db_path, "2026-11-24 00:00")  # first date of --period 7d
    _inquiry(db_path, "2026-11-23 23:59")  # the day before
    text = _report(db_path, capsys, "7d")
    assert _metric(text, report.LABEL_INQUIRIES) == "1"


def test_working_day_same_date_is_within_target(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, "2026-11-27 10:00")  # Friday
    _event(db_path, lead, "acknowledgement", "2026-11-27 23:30")
    assert _ack_counts(_report(db_path, capsys)) == ("1", "0", "0")


def test_working_day_next_date_is_outside_target(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, "2026-11-27 10:00")  # Friday
    _event(db_path, lead, "acknowledgement", "2026-11-28 08:00")
    assert _ack_counts(_report(db_path, capsys)) == ("0", "1", "0")


def test_saturday_acknowledged_monday_is_within_target(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, "2026-11-28 10:00")  # Saturday
    _event(db_path, lead, "acknowledgement", "2026-11-30 16:00")  # Monday
    assert _ack_counts(_report(db_path, capsys)) == ("1", "0", "0")


def test_saturday_acknowledged_tuesday_is_outside_target(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, "2026-11-21 10:00")  # Saturday
    _event(db_path, lead, "acknowledgement", "2026-11-24 09:00")  # Tuesday
    assert _ack_counts(_report(db_path, capsys)) == ("0", "1", "0")


def test_only_voided_acknowledgement_is_not_acknowledged(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, "2026-11-27 10:00")
    ack = _event(db_path, lead, "acknowledgement", "2026-11-27 11:00")
    _void(db_path, lead, ack)
    assert _ack_counts(_report(db_path, capsys)) == ("0", "0", "1")


def test_no_acknowledgement_is_not_acknowledged(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _inquiry(db_path, "2026-11-27 10:00")
    assert _ack_counts(_report(db_path, capsys)) == ("0", "0", "1")


def test_earliest_acknowledgement_decides(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    on_time = _inquiry(db_path, "2026-11-27 10:00")
    _event(db_path, on_time, "acknowledgement", "2026-11-28 09:00")  # logged first, later
    _event(db_path, on_time, "acknowledgement", "2026-11-27 12:00")  # earliest: within
    late = _inquiry(db_path, "2026-11-25 10:00")  # Wednesday
    _event(db_path, late, "acknowledgement", "2026-11-26 09:00")  # earliest: outside
    _event(db_path, late, "acknowledgement", "2026-11-26 10:00")
    assert _ack_counts(_report(db_path, capsys)) == ("1", "1", "0")


def test_voided_earliest_falls_back_to_next(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, "2026-11-27 10:00")
    first = _event(db_path, lead, "acknowledgement", "2026-11-27 11:00")
    _event(db_path, lead, "acknowledgement", "2026-11-28 11:00")
    _void(db_path, lead, first)
    assert _ack_counts(_report(db_path, capsys)) == ("0", "1", "0")


def test_test_inquiry_is_not_in_ack_counts(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, "2026-11-27 10:00", test=True)
    _event(db_path, lead, "acknowledgement", "2026-11-27 11:00")
    assert _ack_counts(_report(db_path, capsys)) == ("0", "0", "0")


def test_inquiry_before_period_is_not_in_ack_counts(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _inquiry(db_path, "2026-11-20 10:00")
    assert _ack_counts(_report(db_path, capsys, "7d")) == ("0", "0", "0")


def test_all_ack_outcomes_together(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    within = _inquiry(db_path, "2026-11-27 10:00")
    _event(db_path, within, "acknowledgement", "2026-11-27 11:00")
    outside = _inquiry(db_path, "2026-11-27 10:30")
    _event(db_path, outside, "acknowledgement", "2026-11-28 11:00")
    _inquiry(db_path, "2026-11-27 11:00")
    assert _ack_counts(_report(db_path, capsys)) == ("1", "1", "1")


def test_missed_and_returned_calls(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lead = _inquiry(db_path, "2026-10-20 10:00")
    tester = _inquiry(db_path, "2026-10-20 11:00", test=True)
    _event(db_path, lead, "missed_call", "2026-11-20 10:00")
    _event(db_path, lead, "missed_call", "2026-11-21 10:00")
    voided = _event(db_path, lead, "missed_call", "2026-11-22 10:00")
    _void(db_path, lead, voided)
    _event(db_path, tester, "missed_call", "2026-11-22 11:00")
    _event(db_path, lead, "call_returned", "2026-11-20 12:00")
    returned_void = _event(db_path, lead, "call_returned", "2026-11-21 12:00")
    _void(db_path, lead, returned_void)
    _event(db_path, tester, "call_returned", "2026-11-22 12:00")
    _event(db_path, lead, "call_returned", "2026-10-30 12:00")  # before the period
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_MISSED_CALLS) == "2"
    assert _metric(text, report.LABEL_RETURNED_CALLS) == "1"


def test_working_day_and_deadline() -> None:
    assert report.working_day(date(2026, 11, 27))  # Friday
    assert not report.working_day(date(2026, 11, 28))  # Saturday
    assert not report.working_day(date(2026, 11, 29))  # Sunday
    assert report.ack_deadline(date(2026, 11, 27)) == date(2026, 11, 27)
    assert report.ack_deadline(date(2026, 11, 28)) == date(2026, 11, 30)
    assert report.ack_deadline(date(2026, 11, 29)) == date(2026, 11, 30)
