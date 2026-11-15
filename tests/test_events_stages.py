"""Tests for log-event --stage: R-14 stages per lead type and the stage_change record."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

AT = "2026-11-16 09:30"
AT_UTC = "2026-11-16T16:30:00Z"
NOW = "2026-12-01T00:00:00Z"
NEED = "needs 4,000 sq ft office TI by March"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Lead 1 inbound and 2 direct_candidate (candidate); 3 relationship (identified)."""
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    code = main(
        [
            "log-inbound",
            "--db",
            str(path),
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
    conn = db.connect(path)
    try:
        conn.execute(
            "INSERT INTO leads (id, type, stage) VALUES (2, 'direct_candidate', 'candidate')"
        )
        conn.execute(
            "INSERT INTO leads (id, type, stage) VALUES (3, 'relationship_prospect', 'identified')"
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _event(db_path: Path, *args: str) -> int:
    return main(["log-event", "--db", str(db_path), *args])


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _stage(db_path: Path, lead_id: int) -> str:
    return str(_rows(db_path, "SELECT stage FROM leads WHERE id = ?", (lead_id,))[0][0])


def _activity_count(db_path: Path) -> int:
    return int(_rows(db_path, "SELECT count(*) FROM activities")[0][0])


def _move(db_path: Path, lead_id: int, stage: str) -> int:
    extra = ["--need", NEED] if stage == events.QUALIFIED_STAGE else []
    return _event(db_path, str(lead_id), "call", "--at", AT, "--stage", stage, *extra)


def test_stage_lists_match_r14() -> None:
    assert events.DIRECT_STAGES == (
        "candidate",
        "researched",
        "contacted_or_replied",
        "buyer_need_confirmed",
        "walkthrough",
        "proposal",
        "won",
        "lost",
        "closed_no_fit",
    )
    assert events.RELATIONSHIP_STAGES == (
        "identified",
        "researched",
        "introduced",
        "responded",
        "active_relationship",
        "closed_no_fit",
    )
    assert events.STAGES_BY_LEAD_TYPE == {
        "inbound_inquiry": events.DIRECT_STAGES,
        "direct_candidate": events.DIRECT_STAGES,
        "relationship_prospect": events.RELATIONSHIP_STAGES,
    }


def test_call_with_stage_moves_lead_and_records_stage_change(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert _event(db_path, "1", "call", "--at", AT, "--stage", "contacted_or_replied") == EXIT_OK
    assert _stage(db_path, 1) == "contacted_or_replied"
    rows = _rows(
        db_path,
        "SELECT * FROM activities WHERE lead_id = 1 AND type <> 'inquiry_logged' ORDER BY id",
    )
    assert [r["type"] for r in rows] == ["call", "stage_change"]
    call, change = rows
    assert call["occurred_at"] == change["occurred_at"] == AT_UTC
    assert json.loads(change["payload"]) == {
        "from": "candidate",
        "to": "contacted_or_replied",
        "event_activity_id": call["id"],
    }
    assert change["lead_id"] == 1
    assert "stage candidate -> contacted_or_replied" in capsys.readouterr().out


def test_event_without_stage_prints_no_stage_suffix(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert _event(db_path, "1", "call", "--at", AT) == EXIT_OK
    assert "stage" not in capsys.readouterr().out
    assert _rows(db_path, "SELECT count(*) FROM activities WHERE type = 'stage_change'")[0][0] == 0


@pytest.mark.parametrize("lead_id", [1, 2])
@pytest.mark.parametrize("stage", [s for s in events.DIRECT_STAGES if s != "candidate"])
def test_every_direct_stage_is_accepted(db_path: Path, lead_id: int, stage: str) -> None:
    assert _move(db_path, lead_id, stage) == EXIT_OK
    assert _stage(db_path, lead_id) == stage


@pytest.mark.parametrize("stage", [s for s in events.RELATIONSHIP_STAGES if s != "identified"])
def test_every_relationship_stage_is_accepted(db_path: Path, stage: str) -> None:
    assert _move(db_path, 3, stage) == EXIT_OK
    assert _stage(db_path, 3) == stage


def test_moves_in_any_order(db_path: Path) -> None:
    for stage in ("won", "researched", "closed_no_fit", "candidate", "buyer_need_confirmed"):
        assert _move(db_path, 1, stage) == EXIT_OK
        assert _stage(db_path, 1) == stage
    for stage in ("closed_no_fit", "identified", "active_relationship", "introduced"):
        assert _move(db_path, 3, stage) == EXIT_OK
        assert _stage(db_path, 3) == stage
    changes = _rows(
        db_path, "SELECT payload FROM activities WHERE type = 'stage_change' AND lead_id = 1"
    )
    froms = [json.loads(r[0])["from"] for r in changes]
    assert froms == ["candidate", "won", "researched", "closed_no_fit", "candidate"]


@pytest.mark.parametrize(
    ("lead_id", "stage", "allowed"),
    [
        (1, "introduced", events.DIRECT_STAGES),
        (2, "active_relationship", events.DIRECT_STAGES),
        (3, "walkthrough", events.RELATIONSHIP_STAGES),
        (1, "bogus", events.DIRECT_STAGES),
        (3, "bogus", events.RELATIONSHIP_STAGES),
        (1, "candidate", events.DIRECT_STAGES),
        (3, "identified", events.RELATIONSHIP_STAGES),
    ],
)
def test_disallowed_or_current_stage_is_refused(
    db_path: Path,
    lead_id: int,
    stage: str,
    allowed: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    before_stage = _stage(db_path, lead_id)
    before = _activity_count(db_path)
    assert _event(db_path, str(lead_id), "call", "--at", AT, "--stage", stage) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    for name in allowed:
        assert name in err
    assert _activity_count(db_path) == before
    assert _stage(db_path, lead_id) == before_stage


def test_failed_stage_change_insert_rolls_back(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(
            "CREATE TRIGGER fail_stage_change BEFORE INSERT ON activities"
            " WHEN NEW.type = 'stage_change' BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
        conn.commit()
    finally:
        conn.close()
    before = _activity_count(db_path)
    assert _event(db_path, "1", "call", "--at", AT, "--stage", "researched") == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
    assert _activity_count(db_path) == before
    assert _stage(db_path, 1) == "candidate"


def test_log_event_rolls_back_on_failure_in_the_same_connection(db_path: Path) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(
            "CREATE TRIGGER fail_stage_change BEFORE INSERT ON activities"
            " WHEN NEW.type = 'stage_change' BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
        conn.commit()
        before = conn.execute("SELECT count(*) FROM activities").fetchone()[0]
        event = events.validate_event(
            events.RawEvent(lead_id=1, type="call", at=AT, stage="researched"), NOW
        )
        with pytest.raises(sqlite3.Error):
            events.log_event(conn, event)
        assert not conn.in_transaction
        assert conn.execute("SELECT count(*) FROM activities").fetchone()[0] == before
        assert conn.execute("SELECT stage FROM leads WHERE id = 1").fetchone()[0] == "candidate"
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("lead_id", "extra", "allowed"),
    [
        (3, ["--stage", "buyer_need_confirmed"], events.RELATIONSHIP_STAGES),
        (3, ["--stage", "buyer_need_confirmed", "--need", "x"], events.RELATIONSHIP_STAGES),
        (1, ["--stage", "bogus", "--need", "x"], events.DIRECT_STAGES),
        (1, ["--stage", "introduced", "--procurement-url", "ftp://x/y"], events.DIRECT_STAGES),
        (3, ["--stage", "walkthrough", "--need", "x"], events.RELATIONSHIP_STAGES),
    ],
)
def test_out_of_list_stage_lists_allowed_stages_even_with_qualification_flags(
    db_path: Path,
    lead_id: int,
    extra: list[str],
    allowed: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    before_stage = _stage(db_path, lead_id)
    before = _activity_count(db_path)
    assert _event(db_path, str(lead_id), "call", "--at", AT, *extra) == EXIT_REFUSED
    err = capsys.readouterr().err
    assert err.startswith("error: stage:")
    for name in allowed:
        assert name in err
    assert _activity_count(db_path) == before
    assert _stage(db_path, lead_id) == before_stage
