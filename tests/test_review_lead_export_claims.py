# sir-target: tests/test_review_lead_export_claims.py
"""The lead export carries each claim's effective status, not the claims file's."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"


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
            "INSERT INTO leads (id, type, stage, organization_id) VALUES"
            " (1, 'direct_candidate', 'researched', 1)"
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
                        "status": "verified",
                        "evidence": "Founder email.",
                        "verified_by": "Pat",
                        "verified_at": "2026-11-01",
                    },
                    {
                        "id": "free-quotes",
                        "text": "Always free quotes.",
                        "status": "prohibited",
                        "evidence": "Legal said no.",
                        "verified_by": None,
                        "verified_at": None,
                    },
                    {
                        "id": "licensed",
                        "text": "Licensed in Utah.",
                        "status": "unverified",
                        "evidence": "Founder email.",
                        "verified_by": None,
                        "verified_at": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    cfg = tmp_path / "pilot.yaml"
    cfg.write_text(
        "sending:\n"
        '  sender_identity: "Cottonwood Contractors"\n'
        '  postal_address: "1 Main St, Sandy, UT 84070"\n'
        '  opt_out_line: "Reply STOP to opt out."\n'
        '  ad_identification: "Advertisement"\n',
        encoding="utf-8",
    )
    return {"db": database, "claims": claims, "config": cfg}


def test_export_uses_effective_claim_status_not_the_files(
    setup: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "review",
            "--lead",
            "1",
            "--json",
            "--claims",
            str(setup["claims"]),
            "--config",
            str(setup["config"]),
            "--db",
            str(setup["db"]),
        ]
    )
    assert code == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    status = {claim["id"]: claim["status"] for claim in data["claims"]}
    # The file says verified, but no 'approve claim' is recorded: effective is unverified.
    assert status == {
        "service-area": "unverified",
        "free-quotes": "prohibited",
        "licensed": "unverified",
    }
