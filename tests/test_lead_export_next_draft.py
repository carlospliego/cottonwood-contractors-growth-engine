"""The lead export says which draft number the skill writes next (CCGE-144)."""

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, review, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
CONFIG = "paths:\n  backup_dir: data/backups\n"
CLAIMS = "claims: []\n"


@pytest.fixture(autouse=True)
def _pinned_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


def _db_with_lead(tmp_path: Path) -> Path:
    path = tmp_path / "pilot.sqlite3"
    db.migrate(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO leads (id, type, stage) VALUES (7, 'direct_candidate', 'researched')"
        )
        conn.commit()
    finally:
        conn.close()
    return path


def test_next_draft_is_1_without_a_drafts_folder(tmp_path: Path) -> None:
    assert review.next_draft_number(tmp_path / "missing", 7) == 1


def test_next_draft_is_1_with_an_empty_drafts_folder(tmp_path: Path) -> None:
    assert review.next_draft_number(tmp_path, 7) == 1


def test_next_draft_follows_the_highest_existing_draft(tmp_path: Path) -> None:
    (tmp_path / "7-1.md").write_text("draft", encoding="utf-8")
    (tmp_path / "7-2.md").write_text("draft", encoding="utf-8")
    assert review.next_draft_number(tmp_path, 7) == 3


def test_a_claims_file_alone_also_takes_its_number(tmp_path: Path) -> None:
    (tmp_path / "7-4.claims.json").write_text("[]", encoding="utf-8")
    assert review.next_draft_number(tmp_path, 7) == 5


def test_other_leads_and_other_files_are_ignored(tmp_path: Path) -> None:
    for name in ("17-5.md", "71-6.md", "8-9.md", "7-x.md", "7-0.md", "7-3.txt", "notes.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert review.next_draft_number(tmp_path, 7) == 1


def test_the_cli_export_carries_next_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = _db_with_lead(tmp_path)
    (tmp_path / "pilot.yaml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "claims.yaml").write_text(CLAIMS, encoding="utf-8")
    drafts = tmp_path / "out" / "drafts"
    drafts.mkdir(parents=True)
    (drafts / "7-1.md").write_text("draft", encoding="utf-8")
    (drafts / "7-2.md").write_text("draft", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "review",
            "--lead",
            "7",
            "--json",
            "--claims",
            "claims.yaml",
            "--config",
            "pilot.yaml",
            "--db",
            str(db_path),
        ]
    )
    assert code == EXIT_OK
    assert json.loads(capsys.readouterr().out)["next_draft"] == 3
