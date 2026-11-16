# sir-target: tests/test_prepare_send_branches.py
"""Tests for untested prepare-send branches: draft read errors, contact, claims file, evidence."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from cottonwood import config, db, send

NOW = "2026-12-01T00:00:00Z"
TODAY = date(2026, 11, 30)
SENDER = "Cottonwood Contractors"
POSTAL = "1 Main St, Sandy, UT 84070"
OPT_OUT = "Reply STOP to opt out."
AD = "Advertisement"
BODY = f"{AD}\n\nHello,\n\n{SENDER}\n{POSTAL}\n{OPT_OUT}\n"


def _settings() -> config.Config:
    return config.Config(
        backup_dir=Path("backups"),
        review=config.ReviewConfig(max_evidence_age_days=30),
        sending=config.SendingConfig(
            sender_identity=SENDER,
            postal_address=POSTAL,
            opt_out_line=OPT_OUT,
            ad_identification=AD,
        ),
    )


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    connection = db.connect(path)
    connection.execute(
        "INSERT INTO contacts (id, name, email, email_norm, eligibility)"
        " VALUES (1, 'Pat (TEST)', 'pat@firm.example.com', 'pat@firm.example.com', 'eligible')"
    )
    connection.execute(
        "INSERT INTO leads (id, type, stage, contact_id) VALUES (1, 'direct_candidate',"
        " 'researched', 1)"
    )
    connection.execute(
        "INSERT INTO evidence (lead_id, url, observed_at, kind)"
        " VALUES (1, 'https://firm.example.com/n', '2026-11-20', 'fact')"
    )
    connection.commit()
    yield connection
    connection.close()


def _prepare(
    conn: sqlite3.Connection, tmp_path: Path, draft: Path | None = None, claims_text: str = "[]"
) -> send.PrepareRefused:
    if draft is None:
        draft = tmp_path / "1-1.md"
        draft.write_text(BODY, encoding="utf-8")
    claims_list = tmp_path / "1-1.claims.json"
    claims_list.write_text(claims_text, encoding="utf-8")
    with pytest.raises(send.PrepareRefused) as info:
        send.prepare_send(
            conn,
            1,
            draft,
            tmp_path / "out",
            tmp_path / "claims.yaml",
            claims_list,
            _settings(),
            TODAY,
            "tester",
            NOW,
        )
    return info.value


def _checks(refused: send.PrepareRefused) -> set[str]:
    return {refusal.check for refusal in refused.refusals}


def test_missing_draft_is_a_send_error(conn: sqlite3.Connection, tmp_path: Path) -> None:
    with pytest.raises(send.SendError, match="draft: no such file"):
        send.prepare_send(
            conn,
            1,
            tmp_path / "absent.md",
            tmp_path / "out",
            tmp_path / "claims.yaml",
            tmp_path / "absent.claims.json",
            _settings(),
            TODAY,
            "tester",
            NOW,
        )


def test_unreadable_draft_is_a_send_error(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = tmp_path / "a-directory.md"
    directory.mkdir()
    with pytest.raises(send.SendError, match="draft: cannot read"):
        send.prepare_send(
            conn,
            1,
            directory,
            tmp_path / "out",
            tmp_path / "claims.yaml",
            tmp_path / "x.claims.json",
            _settings(),
            TODAY,
            "tester",
            NOW,
        )


def test_deleted_contact_is_refused_even_with_an_email(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    conn.execute("UPDATE contacts SET deleted_at = '2026-11-25T00:00:00Z' WHERE id = 1")
    conn.commit()
    refused = _prepare(conn, tmp_path)
    assert "eligibility" in _checks(refused)
    assert any("no contact with an email" in r.detail for r in refused.refusals)


def test_contact_without_email_is_refused(conn: sqlite3.Connection, tmp_path: Path) -> None:
    conn.execute("UPDATE contacts SET email_norm = NULL WHERE id = 1")
    conn.commit()
    assert "eligibility" in _checks(_prepare(conn, tmp_path))


def test_lead_without_contact_is_refused(conn: sqlite3.Connection, tmp_path: Path) -> None:
    conn.execute("UPDATE leads SET contact_id = NULL WHERE id = 1")
    conn.commit()
    assert "eligibility" in _checks(_prepare(conn, tmp_path))


def test_unparseable_claims_file_is_refused(conn: sqlite3.Connection, tmp_path: Path) -> None:
    (tmp_path / "claims.yaml").write_text("{not: valid: [", encoding="utf-8")
    refused = _prepare(conn, tmp_path, claims_text='[{"claim_id": "a", "status": "verified"}]')
    assert "claims" in _checks(refused)


def test_missing_claims_file_is_refused_when_claims_are_used(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    refused = _prepare(conn, tmp_path, claims_text='[{"claim_id": "a", "status": "verified"}]')
    assert "claims" in _checks(refused)


def test_non_date_evidence_is_refused(conn: sqlite3.Connection, tmp_path: Path) -> None:
    conn.execute("UPDATE evidence SET observed_at = 'sometime last week'")
    conn.commit()
    refused = _prepare(conn, tmp_path)
    assert any(r.check == "evidence" and "is not a date" in r.detail for r in refused.refusals)
