"""Tests for mark-reviewed: hand-review results, refusals, replace, and report counts (R-11)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, EXIT_USAGE, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
DAY = "2026-11-30"
STAGES = {
    "direct_candidate": "researched",
    "relationship_prospect": "researched",
    "inbound_inquiry": "candidate",
}


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


def _lead(db_path: Path, lead_type: str = "direct_candidate") -> int:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO leads (type, stage) VALUES (?, ?)", (lead_type, STAGES[lead_type])
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _activities(db_path: Path) -> list[sqlite3.Row]:
    return _rows(db_path, "SELECT * FROM activities ORDER BY id")


def _mark(db_path: Path, lead: int, result: str, *extra: str) -> int:
    return main(
        ["mark-reviewed", str(lead), result, "--reviewer", "founder", *extra, "--db", str(db_path)]
    )


def _report(db_path: Path, capsys: pytest.CaptureFixture[str]) -> list[str]:
    capsys.readouterr()
    code = main(["report", "--from", DAY, "--to", DAY, "--db", str(db_path)])
    assert code == EXIT_OK
    return capsys.readouterr().out.splitlines()


# --- AC 1-2: recorded result and report counts -------------------------------------------


def test_relevant_review_is_recorded_and_counted(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)

    assert _mark(db_path, lead, "relevant", "--date", DAY) == EXIT_OK

    assert capsys.readouterr().out == f"lead {lead}: hand review relevant\n"
    activities = _activities(db_path)
    assert len(activities) == 1
    activity = activities[0]
    assert activity["type"] == "hand_review"
    assert activity["lead_id"] == lead
    assert json.loads(activity["payload"]) == {"result": "relevant", "reviewer": "founder"}
    assert timeutil.local_date(activity["occurred_at"]).isoformat() == DAY
    assert activity["recorded_at"] == NOW
    counted = _rows(
        db_path,
        f"SELECT count(*) FROM activities AS a WHERE {events.COUNTED_ACTIVITIES_SQL}",
    )
    assert counted[0][0] == 1
    lines = _report(db_path, capsys)
    assert "- Hand review direct_candidate relevant: 1" in lines
    assert "- Hand review direct_candidate total: 1" in lines


def test_date_defaults_to_today_in_denver(db_path: Path) -> None:
    lead = _lead(db_path)
    assert _mark(db_path, lead, "irrelevant") == EXIT_OK
    occurred = _activities(db_path)[0]["occurred_at"]
    assert timeutil.local_date(occurred).isoformat() == DAY


def test_earlier_date_is_recorded_on_that_day(db_path: Path) -> None:
    lead = _lead(db_path)
    assert _mark(db_path, lead, "relevant", "--date", "2026-11-02") == EXIT_OK
    occurred = _activities(db_path)[0]["occurred_at"]
    assert timeutil.local_date(occurred).isoformat() == "2026-11-02"


def test_fabricated_partner_counts_as_a_data_quality_failure(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path, "relationship_prospect")

    assert _mark(db_path, lead, "fabricated", "--date", DAY) == EXIT_OK

    lines = _report(db_path, capsys)
    assert "- Hand review relationship_prospect fabricated: 1" in lines
    assert "- Data-quality failures: 1" in lines


# --- AC 3: refusals ----------------------------------------------------------------------


def _refused(
    db_path: Path, capsys: pytest.CaptureFixture[str], lead: int, *extra: str
) -> list[str]:
    capsys.readouterr()
    args = ["mark-reviewed", str(lead), "relevant", *extra, "--db", str(db_path)]
    assert main(args) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert _activities(db_path) == []
    return err.splitlines()


def test_inbound_inquiry_cannot_be_hand_reviewed(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path, "inbound_inquiry")
    err = _refused(db_path, capsys, lead, "--reviewer", "founder")
    assert "lead: type" in err[0]


def test_unknown_lead_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(db_path, capsys, 99, "--reviewer", "founder")
    assert "no lead 99" in err[0]


def test_blank_reviewer_is_refused(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lead = _lead(db_path)
    err = _refused(db_path, capsys, lead, "--reviewer", "   ")
    assert "reviewer" in err[0]


@pytest.mark.parametrize("value", ["2026-02-30", "2026-12-01", "30/11/2026"])
def test_bad_or_future_date_is_refused(
    db_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    lead = _lead(db_path)
    err = _refused(db_path, capsys, lead, "--reviewer", "founder", "--date", value)
    assert "date" in err[0]


def test_result_outside_the_three_is_a_usage_error(db_path: Path) -> None:
    lead = _lead(db_path)
    assert _mark(db_path, lead, "maybe") == EXIT_USAGE
    assert _activities(db_path) == []


def test_missing_reviewer_is_a_usage_error(db_path: Path) -> None:
    lead = _lead(db_path)
    args = ["mark-reviewed", str(lead), "relevant", "--db", str(db_path)]
    assert main(args) == EXIT_USAGE
    assert _activities(db_path) == []


# --- AC 4: one standing review per lead, --replace ---------------------------------------


def test_second_review_is_refused_naming_the_existing_one(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)
    assert _mark(db_path, lead, "relevant", "--date", DAY) == EXIT_OK
    first_id = _activities(db_path)[0]["id"]
    capsys.readouterr()

    assert _mark(db_path, lead, "irrelevant", "--date", DAY) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "relevant" in err
    assert f"activity {first_id}" in err
    assert len(_activities(db_path)) == 1


def test_replace_voids_the_earlier_review_and_counts_only_the_new_one(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)
    assert _mark(db_path, lead, "relevant", "--date", DAY) == EXIT_OK
    first_id = _activities(db_path)[0]["id"]

    assert _mark(db_path, lead, "irrelevant", "--date", DAY, "--replace") == EXIT_OK

    activities = _activities(db_path)
    assert [row["type"] for row in activities] == ["hand_review", "correction", "hand_review"]
    assert activities[1]["voids_activity_id"] == first_id
    assert activities[1]["lead_id"] == lead
    assert json.loads(activities[2]["payload"])["result"] == "irrelevant"
    lines = _report(db_path, capsys)
    assert "- Hand review direct_candidate relevant: 0" in lines
    assert "- Hand review direct_candidate irrelevant: 1" in lines
    assert "- Hand review direct_candidate total: 1" in lines


def test_replace_twice_keeps_one_standing_review(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)
    assert _mark(db_path, lead, "relevant", "--date", DAY) == EXIT_OK
    assert _mark(db_path, lead, "irrelevant", "--date", DAY, "--replace") == EXIT_OK
    assert _mark(db_path, lead, "fabricated", "--date", DAY, "--replace") == EXIT_OK
    lines = _report(db_path, capsys)
    assert "- Hand review direct_candidate fabricated: 1" in lines
    assert "- Hand review direct_candidate total: 1" in lines


def test_replace_without_an_earlier_review_just_records(db_path: Path) -> None:
    lead = _lead(db_path)
    assert _mark(db_path, lead, "relevant", "--replace") == EXIT_OK
    assert [row["type"] for row in _activities(db_path)] == ["hand_review"]


def test_a_review_on_a_test_lead_still_blocks_a_second_review(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE leads SET is_test = 1 WHERE id = ?", (lead,))
    conn.commit()
    conn.close()
    assert _mark(db_path, lead, "relevant") == EXIT_OK
    assert _mark(db_path, lead, "irrelevant") == EXIT_REFUSED
    assert len(_activities(db_path)) == 1
