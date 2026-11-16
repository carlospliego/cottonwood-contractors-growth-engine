"""Tests for 'review --lead ID --json': the lead export the prepare-outreach skill reads (R-20)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, EXIT_USAGE, main

NOW = "2026-12-01T00:00:00Z"
KEYS = {
    "lead_id",
    "type",
    "stage",
    "organization",
    "contact",
    "verified_facts",
    "hypothesis",
    "evidence",
    "checklist",
    "claims",
    "sending",
    "draftable",
    "blocked_by",
    "next_draft",
}
SENDING = {
    "sender_identity": "Cottonwood Contractors",
    "postal_address": "1 Main St, Sandy, UT 84070",
    "opt_out_line": "Reply STOP to opt out.",
    "ad_identification": "Advertisement",
}


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def setup(tmp_path: Path) -> dict[str, Path]:
    database = tmp_path / "cottonwood.db"
    db.migrate(database)
    conn = sqlite3.connect(database)
    try:
        conn.execute(
            "INSERT INTO organizations (id, name, name_norm, domain_norm, created_at)"
            " VALUES (1, 'Firm (TEST)', 'firm (test)', 'firm.example.com', ?)",
            (NOW,),
        )
        conn.execute(
            "INSERT INTO contacts (id, organization_id, name, email, email_norm, role, eligibility)"
            " VALUES (1, 1, 'Pat Lee (TEST)', 'Pat@Firm.example.com', 'pat@firm.example.com',"
            " 'Owner', 'eligible')"
        )
        conn.execute(
            "INSERT INTO leads (id, type, stage, organization_id, contact_id, hypothesis,"
            " verified_facts) VALUES (1, 'direct_candidate', 'researched', 1, 1,"
            " 'May need a build-out', ?)",
            (json.dumps(["Announced a second office"]),),
        )
        conn.execute(
            "INSERT INTO leads (id, type, stage) VALUES (2, 'direct_candidate', 'researched')"
        )
        conn.execute(
            "INSERT INTO evidence (lead_id, url, observed_at, kind, excerpt)"
            " VALUES (1, 'https://firm.example.com/news', '2026-11-20', 'fact',"
            " 'We are opening a second office.')"
        )
        conn.commit()
    finally:
        conn.close()
    claims = tmp_path / "claims.yaml"
    claims.write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "id": "service-area",
                        "text": "Serves four counties.",
                        "status": "unverified",
                        "evidence": "Founder email.",
                        "verified_by": None,
                        "verified_at": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    cfg = tmp_path / "pilot.yaml"
    lines = ["sending:"] + [f"  {key}: {json.dumps(value)}" for key, value in SENDING.items()]
    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"db": database, "claims": claims, "config": cfg, "tmp": tmp_path}


def _export(setup: dict[str, Path], *extra: str, lead: str = "1") -> int:
    return main(
        [
            "review",
            "--lead",
            lead,
            "--json",
            "--claims",
            str(setup["claims"]),
            "--config",
            str(setup["config"]),
            *extra,
            "--db",
            str(setup["db"]),
        ]
    )


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    return []


def test_a_draftable_lead_exports_without_an_address(
    setup: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _export(setup) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert set(data) == KEYS
    assert data["lead_id"] == 1
    assert set(data["contact"]) == {"id", "name", "role", "eligibility", "suppressed"}
    assert data["contact"]["suppressed"] is False
    assert data["claims"] == [
        {"id": "service-area", "text": "Serves four counties.", "status": "unverified"}
    ]
    assert data["sending"] == SENDING
    assert data["verified_facts"] == ["Announced a second office"]
    assert data["evidence"][0]["url"] == "https://firm.example.com/news"
    assert data["draftable"] is True
    assert data["blocked_by"] == []
    assert not [s for s in _strings(data) if "@" in s]


def test_a_suppressed_contact_is_not_draftable(
    setup: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["suppress", "pat@firm.example.com", "--reason", "asked", "--db", str(setup["db"])]
    assert main(args) == EXIT_OK
    capsys.readouterr()
    assert _export(setup) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["draftable"] is False
    assert "suppressed" in data["blocked_by"]
    assert data["contact"]["suppressed"] is True


def test_a_lead_without_a_contact_is_not_draftable(
    setup: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _export(setup, lead="2") == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["contact"] is None
    assert data["draftable"] is False
    assert "no_contact_email" in data["blocked_by"]


def test_out_writes_the_same_export(
    setup: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _export(setup) == EXIT_OK
    printed = json.loads(capsys.readouterr().out)
    target = setup["tmp"] / "OUT" / "lead.json"
    assert _export(setup, "--out", str(target)) == EXIT_OK
    assert capsys.readouterr().out == f"lead export written: {target}\n"
    assert json.loads(target.read_text(encoding="utf-8")) == printed


def test_an_unknown_lead_is_refused(
    setup: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _export(setup, lead="99") == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: lead:")


def test_lead_without_json_is_a_usage_error(setup: dict[str, Path]) -> None:
    assert main(["review", "--lead", "1", "--db", str(setup["db"])]) == EXIT_USAGE
