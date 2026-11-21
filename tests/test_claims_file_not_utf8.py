# sir-target: tests/test_claims_file_not_utf8.py
"""A claims file that is not UTF-8 is refused with an error line, not a traceback (R-19).

F-correctness-3: load_claims caught FileNotFoundError and OSError around read_text, but a
UnicodeDecodeError is a ValueError, so 'claims' and 'approve claim' crashed on such a file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_REFUSED, main

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


@pytest.fixture
def bad_claims(tmp_path: Path) -> Path:
    path = tmp_path / "claims.yaml"
    path.write_bytes(b"\xff\xfe")
    return path


def _activity_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
    finally:
        conn.close()


def test_claims_refuses_a_file_that_is_not_utf8(
    db_path: Path, bad_claims: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    code = main(["claims", "--claims", str(bad_claims), "--db", str(db_path)])
    assert code == EXIT_REFUSED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [f"error: {bad_claims}: file: is not UTF-8 text (byte 0)"]


def test_approve_claim_refuses_a_file_that_is_not_utf8(
    db_path: Path, bad_claims: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    code = main(
        [
            "approve",
            "claim",
            "service-area",
            "--approver",
            "Founder",
            "--reference",
            "r",
            "--claims",
            str(bad_claims),
            "--db",
            str(db_path),
        ]
    )
    assert code == EXIT_REFUSED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        f"error: claims: {bad_claims}: file: is not UTF-8 text (byte 0)"
    ]
    assert _activity_count(db_path) == 0


def test_a_bad_byte_after_valid_text_names_its_offset(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "claims.yaml"
    path.write_bytes(b"claims: []\n# caf\xe9\n")  # Latin-1 e-acute at byte 16
    capsys.readouterr()
    assert main(["claims", "--claims", str(path), "--db", str(db_path)]) == EXIT_REFUSED
    assert capsys.readouterr().err.splitlines() == [
        f"error: {path}: file: is not UTF-8 text (byte 16)"
    ]
