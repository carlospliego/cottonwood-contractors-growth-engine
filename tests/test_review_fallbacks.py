# sir-target: tests/test_review_fallbacks.py
"""Fallbacks in the review's candidate queues: bad checklist JSON, bad dates, bad payloads.

F-testing-1: each unreadable value must show as unknown or '—' in its row; removing a fallback
would crash the whole review instead, and no test covered that.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
CONFIG = """\
paths:
  backup_dir: data/backups
review:
  max_evidence_age_days: 30
  checklists:
    direct_candidate:
      - key: direct_signal
        label: Current, directly sourced signal
      - key: fit
        label: Fits the service area
"""


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "pilot.yaml"
    cfg.write_text(CONFIG, encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(cfg))
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _exec(
    db_path: Path, sql: str, params: tuple[object, ...] = (), *, unchecked: bool = False
) -> int:
    conn = sqlite3.connect(db_path)
    try:
        if unchecked:
            # Plant a row the schema's CHECK constraints would refuse (a corrupted or legacy row).
            conn.execute("PRAGMA ignore_check_constraints = ON")
        cursor = conn.execute(sql, params)
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def _lead(db_path: Path, checklist: str | None) -> int:
    return _exec(
        db_path,
        "INSERT INTO leads (type, stage, checklist) VALUES ('direct_candidate', 'researched', ?)",
        (checklist,),
    )


def _evidence(db_path: Path, lead: int, observed: str) -> None:
    _exec(
        db_path,
        "INSERT INTO evidence (lead_id, url, observed_at, kind) VALUES (?, 'https://e.test', ?,"
        " 'fact')",
        (lead, observed),
    )


def _hand_review(db_path: Path, lead: int, payload: str) -> None:
    _exec(
        db_path,
        "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at)"
        " VALUES (?, 'hand_review', ?, 'tester', ?, ?)",
        (lead, payload, NOW, NOW),
        unchecked=True,
    )


def _rows(db_path: Path, capsys: pytest.CaptureFixture[str]) -> dict[int, dict[str, str]]:
    """The direct-candidate rows of 'cottonwood review', each keyed by its column header."""
    capsys.readouterr()
    assert main(["review", "--db", str(db_path)]) == EXIT_OK
    lines = capsys.readouterr().out.splitlines()
    start = lines.index("## Direct candidates")
    end = lines.index("## Relationship prospects")
    table = [ln for ln in lines[start:end] if ln.startswith("|")]
    header, rows = _cells(table[0]), [_cells(ln) for ln in table[2:]]
    assert {"direct_signal", "fit", "Yes", "Evidence age (days)", "Hand review"} <= set(header)
    return {int(row[0]): dict(zip(header, row, strict=True)) for row in rows}


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split(" | ")]


CHECKLIST = ("direct_signal", "fit")


def test_unreadable_checklists_read_as_unknown(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    malformed = _lead(db_path, "not json")
    non_dict = _lead(db_path, "[1, 2]")
    empty_answer = _lead(db_path, '{"direct_signal": "", "fit": "yes"}')
    rows = _rows(db_path, capsys)
    for lead in (malformed, non_dict):
        assert [rows[lead][key] for key in CHECKLIST] == ["unknown", "unknown"]
        assert rows[lead]["Yes"] == "0"
    assert [rows[empty_answer][key] for key in CHECKLIST] == ["unknown", "yes"]
    assert rows[empty_answer]["Yes"] == "1"


def test_non_iso_evidence_date_shows_no_age(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = _lead(db_path, None)
    _evidence(db_path, bad, "last week")
    good = _lead(db_path, None)
    _evidence(db_path, good, "2026-11-20T10:00:00Z")
    rows = _rows(db_path, capsys)
    assert rows[bad]["Evidence age (days)"] == "—"
    assert rows[good]["Evidence age (days)"] == "10"


def test_unreadable_hand_review_payload_shows_blank(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    not_json = _lead(db_path, None)
    _hand_review(db_path, not_json, "not json")
    not_object = _lead(db_path, None)
    _hand_review(db_path, not_object, '"relevant"')
    wrong_type = _lead(db_path, None)
    _hand_review(db_path, wrong_type, '{"result": 5}')
    fine = _lead(db_path, None)
    _hand_review(db_path, fine, '{"result": "relevant", "reviewer": "x"}')
    rows = _rows(db_path, capsys)
    assert rows[not_json]["Hand review"] == "—"
    assert rows[not_object]["Hand review"] == "—"
    assert rows[wrong_type]["Hand review"] == "—"
    assert rows[fine]["Hand review"] == "relevant"
