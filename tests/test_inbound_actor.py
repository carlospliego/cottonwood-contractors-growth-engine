# sir-target: tests/test_inbound_actor.py
"""--actor is stored on the inquiry activity, and a blank one is refused (F-testing-4)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

LOG_ARGS = (
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


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _actors(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return [str(row[0]) for row in conn.execute("SELECT actor FROM activities ORDER BY id")]
    finally:
        conn.close()


def test_actor_founder_is_stored_on_the_activity(db_path: Path) -> None:
    assert main(["log-inbound", "--db", str(db_path), *LOG_ARGS, "--actor", "founder"]) == EXIT_OK
    assert _actors(db_path) == ["founder"]


def test_actor_defaults_to_the_developer(db_path: Path) -> None:
    assert main(["log-inbound", "--db", str(db_path), *LOG_ARGS]) == EXIT_OK
    assert _actors(db_path) == ["developer"]


@pytest.mark.parametrize("actor", ["  ", "", "\t"])
def test_blank_actor_exits_1_naming_actor(
    db_path: Path, capsys: pytest.CaptureFixture[str], actor: str
) -> None:
    code = main(["log-inbound", "--db", str(db_path), *LOG_ARGS, "--actor", actor])

    assert code == EXIT_REFUSED
    assert "actor" in capsys.readouterr().err
    assert _actors(db_path) == []
