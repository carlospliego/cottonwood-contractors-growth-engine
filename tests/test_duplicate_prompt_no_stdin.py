# sir-target: tests/test_duplicate_prompt_no_stdin.py
"""With stdin closed (sys.stdin is None) a duplicate is refused, not an AttributeError."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

ARGS = (
    "--channel",
    "form",
    "--received",
    "2026-11-16 09:30",
    "--segment",
    "commercial",
    "--name",
    "Pat Lee",
    "--email",
    "pat@example.com",
)


def _leads(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("SELECT count(*) FROM leads").fetchone()[0])
    finally:
        conn.close()


def test_duplicate_with_no_stdin_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    assert main(["log-inbound", "--db", str(path), *ARGS]) == EXIT_OK
    capsys.readouterr()

    monkeypatch.setattr(sys, "stdin", None)
    assert main(["log-inbound", "--db", str(path), *ARGS]) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert "refused: duplicate not confirmed" in err
    assert "AttributeError" not in err
    assert _leads(path) == 1


def test_confirm_flag_still_saves_with_no_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    assert main(["log-inbound", "--db", str(path), *ARGS]) == EXIT_OK

    monkeypatch.setattr(sys, "stdin", None)
    args = ["log-inbound", "--db", str(path), *ARGS, "--confirm-duplicate"]
    assert main(args) == EXIT_OK
    assert _leads(path) == 2
