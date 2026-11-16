# sir-target: tests/test_report_reimport_not_recounted.py
"""A matched re-import that only adds evidence is not counted as research or a referral again."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
PERIOD = ("--from", "2026-11-01", "--to", "2026-11-15")
IN_PERIOD = "2026-11-05T17:00:00Z"
BEFORE_PERIOD = "2026-10-20T17:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


def _imported(db_path: Path, lead_id: int, at: str, created: bool) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at)"
            " VALUES (?, 'imported', ?, 'developer', ?, ?)",
            (lead_id, json.dumps({"created": created, "new_evidence": 1}), at, NOW),
        )
        conn.commit()
    finally:
        conn.close()


def test_matched_reimport_is_not_counted_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cottonwood.db"
    db.migrate(db_path)
    conn = db.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO leads (id, type, stage) VALUES (1, 'relationship_prospect', 'identified')"
        )
        conn.execute(
            "INSERT INTO leads (id, type, stage, referred_by)"
            " VALUES (2, 'direct_candidate', 'candidate', 1)"
        )
        conn.commit()
    finally:
        conn.close()
    # Both leads were created before the period; only matched re-imports fall inside it.
    _imported(db_path, 1, BEFORE_PERIOD, True)
    _imported(db_path, 2, BEFORE_PERIOD, True)
    _imported(db_path, 1, IN_PERIOD, False)
    _imported(db_path, 2, IN_PERIOD, False)
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), *PERIOD]) == EXIT_OK
    text = capsys.readouterr().out
    assert f"- {report.LABEL_RESEARCHED_DIRECT}: 0" in text
    assert f"- {report.LABEL_RESEARCHED_PARTNERS}: 0" in text
    assert f"- {report.LABEL_REFERRED}: 0" in text
