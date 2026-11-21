# sir-target: tests/test_prepare_send_payload_and_lead.py
"""prepare-send records the approvals it relied on, and only the lead's own approvals count (R-21).

F-testing-3 (review 20261115-191126): the ready-draft test checked the draft_prepared payload's
keys but not its values, and no test gave the approvals to a different lead, so a query that
dropped 'lead_id = ?' or recorded the wrong approval id would pass.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sqlite3

import pytest
from test_prepare_send import (  # noqa: F401  (pytest fixtures)
    EMAIL,
    NOW,
    REF,
    Setup,
    _assert_refused,
    fixed_now,
    ready,
)

from cottonwood import db
from cottonwood.cli import EXIT_OK


def _payload(row: sqlite3.Row) -> dict[str, object]:
    value = json.loads(row["payload"])
    assert isinstance(value, dict)
    return value


def _approvals(setup: Setup, scope: str, lead: int = 1) -> list[int]:
    return [
        int(row["id"])
        for row in setup.activities("approval")
        if row["lead_id"] == lead and _payload(row)["scope"] == scope
    ]


def _void(setup: Setup, activity_id: int) -> None:
    setup.sql(
        "INSERT INTO activities (lead_id, type, payload, actor, occurred_at, recorded_at,"
        " voids_activity_id) VALUES (1, 'correction', '{}', 'developer', ?, ?, ?)",
        (NOW, NOW, activity_id),
    )


def _approve_lead(setup: Setup, lead: int = 1) -> None:
    args = ["approve", "lead", str(lead), "--approver", "Founder", "--reference", REF]
    assert setup.run(*args) == EXIT_OK


def _approve_draft(setup: Setup, lead: int = 1) -> None:
    args = ["approve", "draft", str(setup.draft), "--lead", str(lead), "--approver", "Founder"]
    assert setup.run(*args, "--reference", REF) == EXIT_OK


def test_the_payload_names_the_draft_digest_and_the_newest_standing_approvals(
    ready: Setup,  # noqa: F811
) -> None:
    # The fixture approved the lead and the draft once; approve each again so "newest" matters,
    # then add a newer lead approval and void it, so the newest *standing* one must be chosen.
    _approve_lead(ready)
    _approve_draft(ready)
    _approve_lead(ready)
    *_, newest_lead = _approvals(ready, "lead")
    _void(ready, newest_lead)
    lead_ids = _approvals(ready, "lead")
    draft_ids = _approvals(ready, "draft")
    assert len(lead_ids) == 3 and len(draft_ids) == 2
    expected_lead, expected_draft = lead_ids[1], draft_ids[1]

    assert ready.prepare() == EXIT_OK
    [prepared] = ready.activities("draft_prepared")
    payload = _payload(prepared)
    assert payload["sha256"] == hashlib.sha256(ready.draft.read_bytes()).hexdigest()
    assert payload["lead_approval_id"] == expected_lead
    assert payload["draft_approval_id"] == expected_draft
    assert payload["draft"] == ready.draft.as_posix()
    assert payload["sendable"] == (ready.out / ready.draft.name).as_posix()


def test_another_leads_approvals_do_not_satisfy_prepare_send(
    ready: Setup,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Lead 2 shares the contact and gets the same draft bytes approved; lead 1's own approvals
    # are voided, so only lead 2's approvals remain on record.
    ready.sql(
        "INSERT INTO leads (id, type, stage, contact_id) VALUES (2, 'direct_candidate',"
        " 'researched', 1)"
    )
    _approve_lead(ready, lead=2)
    _approve_draft(ready, lead=2)
    for activity_id in _approvals(ready, "lead") + _approvals(ready, "draft"):
        _void(ready, activity_id)
    assert _approvals(ready, "lead", lead=2) and _approvals(ready, "draft", lead=2)

    lines = _assert_refused(ready, capsys, ["approval"])
    assert lines == [
        "refused: approval: no founder approval of lead 1",
        "refused: approval: no founder approval of a draft for lead 1",
    ]


def test_approvals_recorded_only_for_another_lead_do_not_satisfy_prepare_send(
    ready: Setup,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A fresh database where lead 1 was never approved at all: the only lead and draft
    # approvals on record are lead 2's, for the same draft bytes. Everything else is ready.
    fresh = dataclasses.replace(ready, db=ready.tmp / "fresh.db")
    db.migrate(fresh.db)
    fresh.sql(
        "INSERT INTO contacts (id, name, email, email_norm, eligibility)"
        " VALUES (1, 'Pat Lee (TEST)', 'Pat@Firm.example.com', ?, 'eligible')",
        (EMAIL,),
    )
    for lead in (1, 2):
        fresh.sql(
            "INSERT INTO leads (id, type, stage, contact_id) VALUES (?, 'direct_candidate',"
            " 'researched', 1)",
            (lead,),
        )
        fresh.sql(
            "INSERT INTO evidence (lead_id, url, observed_at, kind)"
            " VALUES (?, 'https://firm.example.com/news', '2026-11-20', 'fact')",
            (lead,),
        )
    _approve_lead(fresh, lead=2)
    _approve_draft(fresh, lead=2)
    claim_args = ["approve", "claim", "service-area", "--approver", "Founder"]
    assert fresh.run(*claim_args, "--reference", REF, "--claims", str(fresh.claims)) == EXIT_OK
    assert _approvals(fresh, "lead") == [] and _approvals(fresh, "draft") == []
    assert _approvals(fresh, "lead", lead=2) and _approvals(fresh, "draft", lead=2)

    lines = _assert_refused(fresh, capsys, ["approval"])
    assert lines == [
        "refused: approval: no founder approval of lead 1",
        "refused: approval: no founder approval of a draft for lead 1",
    ]
