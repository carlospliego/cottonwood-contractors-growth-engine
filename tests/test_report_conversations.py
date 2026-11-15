"""Tests for report's conversations, outcomes, hours and KPI sections (R-28, R-16, R-29)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cottonwood import config, db, events, report, timeutil
from cottonwood.cli import EXIT_OK, main

# Denver "today" is 2026-11-30; the tests report on 2026-11-01..2026-11-15 so an entry can be
# dated after the period without being in the future.
NOW = "2026-12-01T00:00:00Z"
PERIOD = ("--from", "2026-11-01", "--to", "2026-11-15")


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


def _scalar(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> int:
    conn = db.connect(db_path)
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()


def _inquiry(db_path: Path, *, test: bool = False) -> int:
    args = [
        "log-inbound",
        "--db",
        str(db_path),
        "--channel",
        "form",
        "--received",
        "2026-10-01 09:00",
        "--segment",
        "commercial",
        "--name",
        "Pat Lee",
        "--confirm-duplicate",
    ]
    if test:
        args.append("--test")
    assert main(args) == EXIT_OK
    return _scalar(db_path, "SELECT max(id) FROM leads")


def _event(db_path: Path, lead_id: int, kind: str, at: str, *args: str) -> int:
    """Log an event and return the event's activity id (not a stage_change's)."""
    code = main(["log-event", "--db", str(db_path), str(lead_id), kind, "--at", at, *args])
    assert code == EXIT_OK
    return _scalar(
        db_path,
        "SELECT max(id) FROM activities WHERE lead_id = ? AND type = ?",
        (lead_id, kind),
    )


def _qualify(db_path: Path, lead_id: int, at: str, kind: str = "remote_screen") -> int:
    return _event(
        db_path, lead_id, kind, at, "--stage", "buyer_need_confirmed", "--need", "4,000 sq ft TI"
    )


def _void(db_path: Path, lead_id: int, activity_id: int, at: str) -> None:
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
            at,
        ]
    )
    assert code == EXIT_OK


def _time(db_path: Path, hours: str, day: str, *args: str) -> None:
    code = main(
        ["log-time", "--db", str(db_path), hours, "--date", day, "--category", "outreach", *args]
    )
    assert code == EXIT_OK


def _report(db_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> str:
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), *(args or PERIOD)]) == EXIT_OK
    return capsys.readouterr().out


def _metric(text: str, label: str) -> str:
    prefix = f"- {label}: "
    matches = [line[len(prefix) :] for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {label!r} line in:\n{text}"
    return matches[0]


def _qualified(db_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    return _metric(_report(db_path, capsys), report.LABEL_QUALIFIED)


def _insert_activity(db_path: Path, lead_id: int, kind: str, at: str) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at)"
            " VALUES (?, ?, ?, 'developer', ?, ?)",
            (lead_id, kind, json.dumps({}), at, NOW),
        )
        conn.commit()
    finally:
        conn.close()


# --- Qualified direct conversations (AC-3.1, AC-5.4) ------------------------------------


def test_two_moves_on_one_lead_count_once(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path)
    _qualify(db_path, lead, "2026-11-02 10:00")
    _event(db_path, lead, "call", "2026-11-03 10:00", "--stage", "contacted_or_replied")
    _qualify(db_path, lead, "2026-11-04 10:00")
    assert (
        _scalar(
            db_path,
            "SELECT count(*) FROM activities WHERE type = 'stage_change'"
            " AND json_extract(payload, '$.to') = 'buyer_need_confirmed'",
        )
        == 2
    )
    assert _qualified(db_path, capsys) == "1"


def test_two_qualified_leads_count_two(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _qualify(db_path, _inquiry(db_path), "2026-11-02 10:00")
    _qualify(db_path, _inquiry(db_path), "2026-11-03 10:00")
    assert _qualified(db_path, capsys) == "2"


def test_voided_move_counts_zero(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lead = _inquiry(db_path)
    move = _qualify(db_path, lead, "2026-11-05 10:00")
    _void(db_path, lead, move, "2026-11-06 10:00")
    assert _qualified(db_path, capsys) == "0"


def test_correction_revert_into_qualified_counts_zero(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path)
    _qualify(db_path, lead, "2026-10-20 10:00")  # before the period
    walk = _event(db_path, lead, "walkthrough", "2026-11-05 10:00", "--stage", "walkthrough")
    _void(db_path, lead, walk, "2026-11-06 10:00")  # reverts to buyer_need_confirmed
    revert = _scalar(
        db_path,
        "SELECT max(id) FROM activities WHERE type = 'stage_change'"
        " AND json_extract(payload, '$.to') = 'buyer_need_confirmed'",
    )
    conn = db.connect(db_path)
    try:
        assert events.is_revert(conn, revert)
    finally:
        conn.close()
    assert _qualified(db_path, capsys) == "0"


def test_test_lead_move_counts_zero(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _qualify(db_path, _inquiry(db_path, test=True), "2026-11-05 10:00")
    assert _qualified(db_path, capsys) == "0"


def test_move_before_period_counts_zero(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _qualify(db_path, _inquiry(db_path), "2026-10-31 23:00")
    assert _qualified(db_path, capsys) == "0"


def test_move_after_period_counts_zero(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _qualify(db_path, _inquiry(db_path), "2026-11-16 00:30")
    assert _qualified(db_path, capsys) == "0"


def test_inquiry_import_and_note_never_qualify(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path)
    _insert_activity(db_path, lead, "inquiry_logged", "2026-11-03T16:00:00Z")
    _insert_activity(db_path, lead, "imported", "2026-11-04T16:00:00Z")
    _event(db_path, lead, "note", "2026-11-05 10:00", "--note", "needs 4,000 sq ft office TI")
    kinds = _scalar(
        db_path,
        "SELECT count(DISTINCT type) FROM activities WHERE lead_id = ?"
        " AND type IN ('inquiry_logged', 'imported', 'note')",
        (lead,),
    )
    assert kinds == 3
    assert _scalar(db_path, "SELECT count(*) FROM activities WHERE type = 'stage_change'") == 0
    assert _qualified(db_path, capsys) == "0"


# --- Outcomes (AC-3.2) ------------------------------------------------------------------


def test_outcome_counts_skip_voided(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lead = _inquiry(db_path)
    for kind in report.OUTCOME_LABELS:
        _event(db_path, lead, kind, "2026-11-05 10:00")
        voided = _event(db_path, lead, kind, "2026-11-06 10:00")
        _void(db_path, lead, voided, "2026-11-07 10:00")
    _event(db_path, lead, "won", "2026-11-20 10:00")  # after the period
    text = _report(db_path, capsys)
    for label in report.OUTCOME_LABELS.values():
        assert _metric(text, label) == "1"


def test_outcomes_on_test_lead_do_not_count(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _inquiry(db_path, test=True)
    for kind in report.OUTCOME_LABELS:
        _event(db_path, lead, kind, "2026-11-05 10:00")
    text = _report(db_path, capsys)
    for label in report.OUTCOME_LABELS.values():
        assert _metric(text, label) == "0"


def test_empty_database_prints_zero_outcomes_and_hours(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = _report(db_path, capsys)
    assert "## Conversations and KPI" in text
    assert "## Hours" in text
    for label in (
        report.LABEL_QUALIFIED,
        *report.OUTCOME_LABELS.values(),
        report.LABEL_FOUNDER_HOURS,
        report.LABEL_FOUNDER_OBSERVED,
        report.LABEL_FOUNDER_ESTIMATED,
        report.LABEL_DEVELOPER_HOURS,
    ):
        assert _metric(text, label) == "0"
    assert _metric(text, report.LABEL_KPI) == "n/a"


# --- Hours (AC-3.3) ---------------------------------------------------------------------


def test_founder_and_developer_hours(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _time(db_path, "2", "2026-11-05")
    _time(db_path, "1", "2026-11-06", "--estimated")
    _time(db_path, "3", "2026-11-07", "--person", "developer")
    _time(db_path, "5", "2026-11-20")  # founder, after the period
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_FOUNDER_HOURS) == "3"
    assert _metric(text, report.LABEL_FOUNDER_OBSERVED) == "2"
    assert _metric(text, report.LABEL_FOUNDER_ESTIMATED) == "1"
    assert _metric(text, report.LABEL_DEVELOPER_HOURS) == "3"
    hours_section = text.split("## Hours", 1)[1]
    developer_lines = [ln for ln in hours_section.splitlines() if "Developer" in ln]
    assert developer_lines == [f"- {report.LABEL_DEVELOPER_HOURS}: 3"]


def test_developer_estimated_hours_are_not_founder_estimated(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _time(db_path, "4", "2026-11-05", "--person", "developer", "--estimated")
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_FOUNDER_HOURS) == "0"
    assert _metric(text, report.LABEL_FOUNDER_ESTIMATED) == "0"
    assert _metric(text, report.LABEL_DEVELOPER_HOURS) == "4"


def test_voided_hours_are_left_out(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _time(db_path, "2", "2026-11-05")
    _time(db_path, "7", "2026-11-05")
    entry = _scalar(db_path, "SELECT max(id) FROM activities WHERE type = 'time_logged'")
    assert main(["log-time", "--db", str(db_path), "--voids", str(entry)]) == EXIT_OK
    assert _metric(_report(db_path, capsys), report.LABEL_FOUNDER_HOURS) == "2"


def test_founder_split_matches_time_totals(db_path: Path) -> None:
    _time(db_path, "2.5", "2026-11-05")
    _time(db_path, "1.25", "2026-11-06", "--estimated")
    _time(db_path, "3", "2026-11-07", "--person", "developer", "--estimated")
    start, end = date(2026, 11, 1), date(2026, 11, 15)
    conn = db.connect(db_path)
    try:
        built = report.build_report(conn, report.Period(start, end), None, NOW)
        totals = events.time_totals(conn, start, end)
    finally:
        conn.close()
    hours = built.hours
    assert hours.founder_observed + hours.founder_estimated == totals.by_person["founder"]
    assert hours.founder_total == Decimal("3.75")
    assert hours.developer == Decimal("3")


# --- KPI (AC-3.4) -----------------------------------------------------------------------


def test_kpi_two_decimals(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _qualify(db_path, _inquiry(db_path), "2026-11-05 10:00")
    _event(db_path, _inquiry(db_path), "partner_conversation", "2026-11-06 10:00")
    _time(db_path, "2", "2026-11-05")
    _time(db_path, "1", "2026-11-06", "--estimated")
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_QUALIFIED) == "1"
    assert _metric(text, report.LABEL_PARTNER) == "1"
    assert _metric(text, report.LABEL_FOUNDER_HOURS) == "3"
    assert _metric(text, report.LABEL_KPI) == "0.67"


def test_kpi_na_with_no_founder_hours(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _qualify(db_path, _inquiry(db_path), "2026-11-05 10:00")
    _time(db_path, "3", "2026-11-05", "--person", "developer")
    assert _metric(_report(db_path, capsys), report.LABEL_KPI) == "n/a"


def test_kpi_function() -> None:
    assert report.kpi(1, 1, Decimal(3)) == Decimal("0.67")
    assert str(report.kpi(1, 0, Decimal(1))) == "1.00"
    assert report.kpi(0, 0, Decimal("0.5")) == Decimal("0.00")
    assert report.kpi(5, 5, Decimal(0)) is None
    assert report.kpi(1, 0, Decimal(8)) == Decimal("0.13")  # 0.125 rounds half up
