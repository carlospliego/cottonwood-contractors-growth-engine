"""Tests for the claims library and claim approvals (R-19)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import claims, config, db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

ROOT = Path(__file__).resolve().parent.parent
NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
REFERENCE = "email 2026-11-30 Re: claims"
SHIPPED_IDS = [
    "fashion-place-attribution",
    "service-area",
    "license-classification",
    "insurance-bonding",
    "prior-company-experience",
]


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


def _entry(claim_id: str, status: str = "unverified", **extra: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": claim_id,
        "text": f"Claim {claim_id}.",
        "status": status,
        "evidence": "Founder email.",
        "verified_by": None,
        "verified_at": None,
    }
    entry.update(extra)
    return entry


def _write(tmp_path: Path, entries: list[dict[str, object]], name: str = "claims.yaml") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"claims": entries}), encoding="utf-8")  # JSON is valid YAML
    return path


def _library(tmp_path: Path) -> Path:
    return _write(
        tmp_path,
        [_entry("service-area"), _entry("never-cheapest", "prohibited"), _entry("licensed")],
    )


def _activities(db_path: Path) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute("SELECT * FROM activities ORDER BY id"))
    finally:
        conn.close()


def _approve_claim(db_path: Path, claims_path: Path, claim_id: str) -> int:
    return main(
        [
            "approve",
            "claim",
            claim_id,
            "--approver",
            "Founder",
            "--reference",
            REFERENCE,
            "--claims",
            str(claims_path),
            "--db",
            str(db_path),
        ]
    )


def _claims(db_path: Path, claims_path: Path) -> int:
    return main(["claims", "--claims", str(claims_path), "--db", str(db_path)])


def _void(db_path: Path, activity_id: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at,"
            " voids_activity_id) VALUES (NULL, 'correction', '{}', 'developer', ?, ?, ?)",
            (NOW, NOW, activity_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- the shipped file -------------------------------------------------------------------


def test_shipped_claims_are_the_five_r19_claims_all_unverified() -> None:
    shipped = claims.load_claims(ROOT / "config" / "claims.yaml")
    assert [claim.id for claim in shipped] == SHIPPED_IDS
    for claim in shipped:
        assert claim.text
        assert claim.evidence
        assert claim.status == "unverified"
        assert claim.verified_by is None
        assert claim.verified_at is None


def test_the_default_path_is_the_shipped_file() -> None:
    assert claims.DEFAULT_CLAIMS_PATH == Path("config/claims.yaml")


# --- loader refusals --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entries", "where", "field"),
    [
        ([{"text": "x", "status": "unverified", "evidence": "y"}], "claims[1]", "id"),
        ([_entry("service-area"), _entry("service-area")], "service-area", "id"),
        ([_entry("Service_Area")], "claims[1]", "id"),
        ([_entry("service-area", text="  ")], "service-area", "text"),
        ([_entry("service-area", evidence="")], "service-area", "evidence"),
        ([_entry("service-area", "maybe")], "service-area", "status"),
        (
            [_entry("service-area", "verified", verified_at="2026-11-30")],
            "service-area",
            "verified_by",
        ),
        (
            [_entry("service-area", "verified", verified_by="Founder", verified_at="30/11/2026")],
            "service-area",
            "verified_at",
        ),
        ([_entry("service-area", verified_by="Founder")], "service-area", "verified_by"),
        (
            [_entry("service-area", "prohibited", verified_at="2026-11-30")],
            "service-area",
            "verified_at",
        ),
    ],
)
def test_a_bad_claims_file_is_refused_naming_file_claim_and_field(
    db_path: Path,
    tmp_path: Path,
    entries: list[dict[str, object]],
    where: str,
    field: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, entries)
    assert _claims(db_path, path) == EXIT_REFUSED
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 1
    assert err[0].startswith("error:")
    assert str(path) in err[0]
    assert where in err[0]
    assert f"{field}:" in err[0]


def test_an_unquoted_yaml_date_reads_as_its_text(tmp_path: Path) -> None:
    path = tmp_path / "claims.yaml"
    path.write_text(
        "claims:\n  - id: service-area\n    text: Four counties.\n    status: verified\n"
        "    evidence: Founder email.\n    verified_by: Founder\n    verified_at: 2026-11-30\n",
        encoding="utf-8",
    )
    [claim] = claims.load_claims(path)
    assert claim.verified_at == "2026-11-30"


# --- approve claim ----------------------------------------------------------------------


def test_a_claim_approval_records_the_approval_and_the_verification(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _library(tmp_path)
    assert _approve_claim(db_path, path, "service-area") == EXIT_OK
    assert capsys.readouterr().out == (
        "approval 1 recorded: claim service-area by Founder; mark it verified in"
        " config/claims.yaml with verified_by: Founder and verified_at: 2026-11-30\n"
    )
    approval, verified = _activities(db_path)
    assert approval["type"] == "approval"
    assert approval["lead_id"] is None
    assert json.loads(approval["payload"]) == {
        "scope": "claim",
        "item": "service-area",
        "approver": "Founder",
        "reference": REFERENCE,
        "approved_on": "2026-11-30",
    }
    assert verified["type"] == "claim_verified"
    assert json.loads(verified["payload"]) == {
        "claim_id": "service-area",
        "approval_activity_id": approval["id"],
        "verified_by": "Founder",
        "verified_at": "2026-11-30",
    }


@pytest.mark.parametrize("claim_id", ["no-such-claim", "never-cheapest"])
def test_an_unknown_or_prohibited_claim_cannot_be_approved(
    db_path: Path, tmp_path: Path, claim_id: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _approve_claim(db_path, _library(tmp_path), claim_id) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: claim:")
    assert _activities(db_path) == []


def test_a_verified_claim_cannot_be_approved_again(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _library(tmp_path)
    assert _approve_claim(db_path, path, "service-area") == EXIT_OK
    before = len(_activities(db_path))
    capsys.readouterr()
    assert _approve_claim(db_path, path, "service-area") == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: claim:")
    assert len(_activities(db_path)) == before


def test_a_voided_verification_allows_a_new_approval(db_path: Path, tmp_path: Path) -> None:
    path = _library(tmp_path)
    assert _approve_claim(db_path, path, "service-area") == EXIT_OK
    verified = _activities(db_path)[1]
    _void(db_path, int(verified["id"]))
    assert _approve_claim(db_path, path, "service-area") == EXIT_OK


# --- effective statuses -----------------------------------------------------------------


def test_claims_agreeing_with_the_approvals_exit_0(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _approve_claim(db_path, _library(tmp_path), "service-area") == EXIT_OK
    capsys.readouterr()
    path = _write(
        tmp_path,
        [
            _entry("service-area", "verified", verified_by="Founder", verified_at="2026-11-30"),
            _entry("never-cheapest", "prohibited"),
            _entry("licensed"),
        ],
        "agreed.yaml",
    )
    assert _claims(db_path, path) == EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        "service-area: verified",
        "never-cheapest: prohibited",
        "licensed: unverified",
    ]


@pytest.mark.parametrize(
    ("verified_by", "verified_at", "approve", "void"),
    [
        ("Founder", "2026-11-30", False, False),  # no approval at all
        ("Someone Else", "2026-11-30", True, False),  # verifier differs
        ("Founder", "2026-11-29", True, False),  # date differs
        ("Founder", "2026-11-30", True, True),  # approval voided by a correction
    ],
)
def test_verified_without_a_matching_approval_is_a_mismatch(
    db_path: Path,
    tmp_path: Path,
    verified_by: str,
    verified_at: str,
    approve: bool,
    void: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if approve:
        assert _approve_claim(db_path, _library(tmp_path), "service-area") == EXIT_OK
    if void:
        _void(db_path, int(_activities(db_path)[1]["id"]))
    capsys.readouterr()
    path = _write(
        tmp_path,
        [_entry("service-area", "verified", verified_by=verified_by, verified_at=verified_at)],
        "marked.yaml",
    )
    assert _claims(db_path, path) == EXIT_REFUSED
    assert capsys.readouterr().out == (
        "service-area: unverified (marked verified but no matching claim approval)\n"
    )


def test_approved_but_still_unverified_in_the_file_is_a_mismatch(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _library(tmp_path)
    assert _approve_claim(db_path, path, "service-area") == EXIT_OK
    capsys.readouterr()
    assert _claims(db_path, path) == EXIT_REFUSED
    assert capsys.readouterr().out.splitlines()[0] == (
        "service-area: unverified (approved on 2026-11-30 by Founder;"
        " mark it verified in the claims file)"
    )


def test_claims_reads_config_claims_yaml_by_default(
    db_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "config").mkdir()
    _write(tmp_path / "config", [_entry("service-area")])
    monkeypatch.chdir(tmp_path)
    assert main(["claims", "--db", str(db_path)]) == EXIT_OK
    assert capsys.readouterr().out == "service-area: unverified\n"
