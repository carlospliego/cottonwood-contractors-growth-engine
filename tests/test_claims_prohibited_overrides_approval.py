# sir-target: tests/test_claims_prohibited_overrides_approval.py
"""A claim the file marks prohibited stays prohibited, even with an approval on record (R-19).

F-testing-5: effective_statuses checks 'prohibited' before it looks at the approvals, but no test
had a claim_verified activity for a prohibited claim, so moving that branch below the approval
check would turn an approved-then-prohibited claim back into 'unverified (approved on ...)'.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import claims, config, db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30


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


def _claims_file(tmp_path: Path, name: str, status: str) -> Path:
    path = tmp_path / name
    path.write_text(
        "claims:\n"
        "  - id: service-area\n"
        "    text: Serves the Salt Lake valley.\n"
        f"    status: {status}\n"
        "    evidence: Founder email.\n"
        "  - id: licensed\n"
        "    text: Licensed in Utah.\n"
        "    status: unverified\n"
        "    evidence: State lookup.\n",
        encoding="utf-8",
    )
    return path


def _approve_service_area(db_path: Path, library: Path) -> None:
    command = ["approve", "claim", "service-area", "--approver", "Founder", "--reference", "r"]
    assert main([*command, "--claims", str(library), "--db", str(db_path)]) == EXIT_OK


def test_a_prohibited_claim_with_an_approval_on_record_is_prohibited(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _approve_service_area(db_path, _claims_file(tmp_path, "claims.yaml", "unverified"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert claims.standing_verification(conn, "service-area") is not None
    finally:
        conn.close()

    prohibited = _claims_file(tmp_path, "prohibited.yaml", "prohibited")
    capsys.readouterr()
    assert main(["claims", "--claims", str(prohibited), "--db", str(db_path)]) == EXIT_OK
    assert capsys.readouterr().out == "service-area: prohibited\nlicensed: unverified\n"


def test_the_same_approval_is_still_reported_while_the_claim_is_unverified(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The contrast: before the founder prohibits it, the approval shows as a note.
    library = _claims_file(tmp_path, "claims.yaml", "unverified")
    _approve_service_area(db_path, library)
    capsys.readouterr()
    main(["claims", "--claims", str(library), "--db", str(db_path)])
    assert capsys.readouterr().out.splitlines()[0] == (
        "service-area: unverified (approved on 2026-11-30 by Founder;"
        " mark it verified in the claims file)"
    )
