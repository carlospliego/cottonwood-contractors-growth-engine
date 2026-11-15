"""Tests for report's prospecting, outreach, replies, data-quality and referral sections.

Covers R-28, R-11 and R-12. Later features write these activity types; the tests insert them
by SQL under the payload contract (hand_review.result, reply.reply_type).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"
PERIOD = ("--from", "2026-11-01", "--to", "2026-11-15")
IN_PERIOD = "2026-11-05T17:00:00Z"
BEFORE_PERIOD = "2026-10-20T17:00:00Z"


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


def _exec(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> int:
    conn = db.connect(db_path)
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


STAGE_BY_TYPE = {
    "direct_candidate": "candidate",
    "relationship_prospect": "identified",
    "inbound_inquiry": "candidate",
}


def _lead(
    db_path: Path,
    lead_type: str = "direct_candidate",
    *,
    test: bool = False,
    lead_id: int | None = None,
    referred_by: int | None = None,
    organization: str | None = None,
    contact: str | None = None,
) -> int:
    org_id = None
    if organization is not None:
        org_id = _exec(
            db_path,
            "INSERT INTO organizations (name, name_norm, created_at) VALUES (?, ?, ?)",
            (organization, organization.lower(), NOW),
        )
    contact_id = None
    if contact is not None:
        contact_id = _exec(db_path, "INSERT INTO contacts (name) VALUES (?)", (contact,))
    return _exec(
        db_path,
        "INSERT INTO leads (id, type, stage, is_test, referred_by, organization_id, contact_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            lead_id,
            lead_type,
            STAGE_BY_TYPE[lead_type],
            1 if test else 0,
            referred_by,
            org_id,
            contact_id,
        ),
    )


def _activity(
    db_path: Path,
    lead_id: int | None,
    kind: str,
    at: str = IN_PERIOD,
    payload: dict[str, object] | None = None,
) -> int:
    return _exec(
        db_path,
        "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at)"
        " VALUES (?, ?, ?, 'developer', ?, ?)",
        (lead_id, kind, json.dumps(payload or {}), at, NOW),
    )


def _void(db_path: Path, lead_id: int | None, activity_id: int) -> None:
    _exec(
        db_path,
        "INSERT INTO activities"
        " (lead_id, type, payload, actor, occurred_at, recorded_at, voids_activity_id)"
        " VALUES (?, 'correction', '{}', 'developer', ?, ?, ?)",
        (lead_id, "2026-11-06T17:00:00Z", NOW, activity_id),
    )


def _report(db_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), *PERIOD]) == EXIT_OK
    return capsys.readouterr().out


def _metric(text: str, label: str) -> str:
    prefix = f"- {label}: "
    matches = [line[len(prefix) :] for line in text.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {label!r} line in:\n{text}"
    return matches[0]


def _hand_label(motion: str, result: str) -> str:
    return f"{report.LABEL_HAND_REVIEW} {motion} {result}"


# --- Research and hand review (AC-4.1) --------------------------------------------------


def test_researched_counts_distinct_leads_by_motion(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _lead(db_path, "direct_candidate")
    second = _lead(db_path, "direct_candidate")
    partner = _lead(db_path, "relationship_prospect")
    tester = _lead(db_path, "direct_candidate", test=True)
    voided_lead = _lead(db_path, "direct_candidate")
    _activity(db_path, first, "imported")
    _activity(db_path, first, "imported", "2026-11-07T17:00:00Z")
    _activity(db_path, second, "imported")
    _activity(db_path, partner, "imported")
    _activity(db_path, tester, "imported")
    _void(db_path, voided_lead, _activity(db_path, voided_lead, "imported"))
    _activity(db_path, _lead(db_path, "direct_candidate"), "imported", BEFORE_PERIOD)
    text = _report(db_path, capsys)
    assert _metric(text, report.LABEL_RESEARCHED_DIRECT) == "2"
    assert _metric(text, report.LABEL_RESEARCHED_PARTNERS) == "1"


def test_hand_review_per_motion_and_result(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    direct = _lead(db_path, "direct_candidate")
    partner = _lead(db_path, "relationship_prospect")
    for result in ("relevant", "irrelevant", "fabricated"):
        _activity(db_path, direct, "hand_review", payload={"result": result})
    _activity(db_path, direct, "hand_review", payload={"result": "relevant"})
    _activity(db_path, partner, "hand_review", payload={"result": "fabricated"})
    _activity(db_path, partner, "hand_review", payload={"result": "unclear"})  # unknown
    voided = _activity(db_path, partner, "hand_review", payload={"result": "relevant"})
    _void(db_path, partner, voided)
    tester = _lead(db_path, "relationship_prospect", test=True)
    _activity(db_path, tester, "hand_review", payload={"result": "irrelevant"})
    text = _report(db_path, capsys)
    assert _metric(text, _hand_label("direct_candidate", "relevant")) == "2"
    assert _metric(text, _hand_label("direct_candidate", "irrelevant")) == "1"
    assert _metric(text, _hand_label("direct_candidate", "fabricated")) == "1"
    assert _metric(text, _hand_label("direct_candidate", report.TOTAL)) == "4"
    assert _metric(text, _hand_label("relationship_prospect", "relevant")) == "0"
    assert _metric(text, _hand_label("relationship_prospect", "irrelevant")) == "0"
    assert _metric(text, _hand_label("relationship_prospect", "fabricated")) == "1"
    assert _metric(text, _hand_label("relationship_prospect", report.TOTAL)) == "2"


def test_empty_database_prints_every_funnel_line_as_zero(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = _report(db_path, capsys)
    for section in (
        "## Prospecting and outreach",
        "## Replies and opt-outs",
        "## Data quality",
        "## Referrals",
    ):
        assert section in text
    labels = [report.LABEL_RESEARCHED_DIRECT, report.LABEL_RESEARCHED_PARTNERS]
    for motion in report.MOTIONS:
        labels += [_hand_label(motion, r) for r in (*report.HAND_REVIEW_RESULTS, report.TOTAL)]
    labels += list(report.OUTREACH_LABELS.values())
    labels += [f"{report.LABEL_REPLIES} {t}" for t in report.REPLY_TYPES]
    labels += [report.LABEL_OPT_OUTS, report.LABEL_DATA_QUALITY, report.LABEL_REFERRED]
    for label in labels:
        assert _metric(text, label) == "0"
    assert "| Partner lead |" not in text


# --- Outreach steps (AC-4.2) ------------------------------------------------------------


def test_outreach_steps_skip_voided(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lead = _lead(db_path)
    for kind in report.OUTREACH_LABELS:
        _activity(db_path, lead, kind)
        _void(db_path, lead, _activity(db_path, lead, kind))
        _activity(db_path, lead, kind, BEFORE_PERIOD)
    text = _report(db_path, capsys)
    for label in report.OUTREACH_LABELS.values():
        assert _metric(text, label) == "1"


# --- Replies and opt-outs (AC-4.3) ------------------------------------------------------


def test_replies_by_type_and_opt_outs(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lead = _lead(db_path)
    for reply_type in report.REPLY_TYPES:
        _activity(db_path, lead, "reply", payload={"reply_type": reply_type})
    _activity(db_path, None, "suppressed")
    text = _report(db_path, capsys)
    for reply_type in report.REPLY_TYPES:
        assert _metric(text, f"{report.LABEL_REPLIES} {reply_type}") == "1"
    assert _metric(text, report.LABEL_OPT_OUTS) == "2"


def test_unknown_or_missing_reply_type_counts_as_other(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)
    _activity(db_path, lead, "reply", payload={"reply_type": "angry"})
    _activity(db_path, lead, "reply")
    _activity(db_path, lead, "reply", payload={"reply_type": "other"})
    text = _report(db_path, capsys)
    assert _metric(text, f"{report.LABEL_REPLIES} other") == "3"
    assert _metric(text, f"{report.LABEL_REPLIES} interested") == "0"


def test_voided_and_out_of_period_replies_and_suppressions_skip(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path)
    _void(db_path, lead, _activity(db_path, lead, "reply", payload={"reply_type": "opt_out"}))
    _activity(db_path, lead, "reply", BEFORE_PERIOD, payload={"reply_type": "opt_out"})
    _void(db_path, lead, _activity(db_path, lead, "suppressed"))
    _activity(db_path, lead, "suppressed", BEFORE_PERIOD)
    text = _report(db_path, capsys)
    assert _metric(text, f"{report.LABEL_REPLIES} opt_out") == "0"
    assert _metric(text, report.LABEL_OPT_OUTS) == "0"


# --- Data quality (AC-4.4) --------------------------------------------------------------


def test_data_quality_failures(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _activity(db_path, None, "import_rejected")
    _activity(db_path, None, "import_rejected")
    _activity(db_path, None, "import_rejected", BEFORE_PERIOD)
    lead = _lead(db_path)
    _activity(db_path, lead, "hand_review", payload={"result": "fabricated"})
    _activity(db_path, lead, "hand_review", payload={"result": "relevant"})
    _void(db_path, lead, _activity(db_path, lead, "hand_review", payload={"result": "fabricated"}))
    assert _metric(_report(db_path, capsys), report.LABEL_DATA_QUALITY) == "3"


# --- Referrals (AC-4.5) -----------------------------------------------------------------


def _table_rows(text: str) -> list[list[str]]:
    section = text.split("## Referrals", 1)[1]
    rows = [ln for ln in section.splitlines() if ln.startswith("| ")]
    return [[c.strip() for c in row.strip("|").split(" | ")] for row in rows[1:]]


def test_referred_leads_per_partner(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _lead(db_path, "relationship_prospect", lead_id=5, organization="Wasatch Brokers | LLC")
    inquiry = _lead(db_path, "inbound_inquiry", referred_by=5)
    _activity(db_path, inquiry, "inquiry_logged")
    imported = _lead(db_path, "direct_candidate", referred_by=5)
    _activity(db_path, imported, "imported")
    _activity(db_path, imported, "inquiry_logged")  # still one referred lead
    early = _lead(db_path, "direct_candidate", referred_by=5)
    _activity(db_path, early, "imported", BEFORE_PERIOD)
    tester = _lead(db_path, "inbound_inquiry", referred_by=5, test=True)
    _activity(db_path, tester, "inquiry_logged")
    _activity(db_path, _lead(db_path, "direct_candidate"), "imported")  # not referred
    text = _report(db_path, capsys)
    assert _table_rows(text) == [["5", "Wasatch Brokers \\| LLC", "2"]]
    assert _metric(text, report.LABEL_REFERRED) == "2"


def test_referrals_group_by_partner_and_fall_back_on_name(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _lead(db_path, "relationship_prospect", lead_id=5, contact="Dana Ruiz")
    _lead(db_path, "relationship_prospect", lead_id=6)
    for partner in (5, 6, 6):
        lead = _lead(db_path, "direct_candidate", referred_by=partner)
        _activity(db_path, lead, "imported")
    text = _report(db_path, capsys)
    assert _table_rows(text) == [["5", "Dana Ruiz", "1"], ["6", "—", "2"]]
    assert _metric(text, report.LABEL_REFERRED) == "3"


def test_no_referred_leads_prints_zero(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _lead(db_path, "relationship_prospect", lead_id=5, organization="Wasatch Brokers")
    early = _lead(db_path, "direct_candidate", referred_by=5)
    _activity(db_path, early, "imported", BEFORE_PERIOD)
    text = _report(db_path, capsys)
    assert _table_rows(text) == []
    assert _metric(text, report.LABEL_REFERRED) == "0"
