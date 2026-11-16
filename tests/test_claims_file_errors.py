# sir-target: tests/test_claims_file_errors.py
"""Claims file error paths through `cottonwood claims` and `cottonwood approve claim` (R-19)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, timeutil
from cottonwood.cli import EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"
REFERENCE = "email 2026-11-30 Re: claims"

BAD_FILES = {
    "malformed-yaml": "claims: [unclosed\n  - {bad",
    "top-level-list": "- id: service-area\n- id: licensed\n",
    "claims-not-a-list": "claims: just some text\n",
    "scalar-entry": "claims:\n  - just a string\n",
}
KINDS = ["missing", *BAD_FILES]


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


def _bad_file(tmp_path: Path, kind: str) -> Path:
    path = tmp_path / "claims.yaml"
    if kind != "missing":
        path.write_text(BAD_FILES[kind], encoding="utf-8")
    return path


def _activity_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0])
    finally:
        conn.close()


@pytest.mark.parametrize("kind", KINDS)
def test_claims_command_refuses_an_unusable_file(
    kind: str, tmp_path: Path, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _bad_file(tmp_path, kind)

    code = main(["claims", "--claims", str(path), "--db", str(db_path)])

    err = capsys.readouterr().err
    assert code == EXIT_REFUSED
    assert err.startswith("error:")
    assert str(path) in err
    if kind != "malformed-yaml":  # the YAML parser's own message spans several lines
        assert len(err.strip().splitlines()) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_approve_claim_refuses_an_unusable_file_and_records_nothing(
    kind: str, tmp_path: Path, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _bad_file(tmp_path, kind)
    before = _activity_count(db_path)

    code = main(
        [
            "approve",
            "claim",
            "service-area",
            "--approver",
            "Founder",
            "--reference",
            REFERENCE,
            "--claims",
            str(path),
            "--db",
            str(db_path),
        ]
    )

    err = capsys.readouterr().err
    assert code == EXIT_REFUSED
    assert err.startswith("error: claims:")
    assert str(path) in err
    assert _activity_count(db_path) == before
