# sir-target: tests/test_review_lead_export_branches.py
"""Lead export branches the main tests leave out (R-20).

F-testing-2 (review 20261115-193520): no test covered a deleted or address-less contact, a
configured checklist, unreadable verified_facts, the evidence order with published_at, or the
organization's fields, so a regression in any of them would pass.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from test_review_lead_export import _export, fixed_now, setup  # noqa: F401  (pytest fixtures)

from cottonwood.cli import EXIT_OK


def _sql(setup: dict[str, Path], statement: str, params: tuple[object, ...] = ()) -> None:  # noqa: F811
    conn = sqlite3.connect(setup["db"])
    try:
        conn.execute(statement, params)
        conn.commit()
    finally:
        conn.close()


def _data(setup: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> dict[str, object]:  # noqa: F811
    capsys.readouterr()
    assert _export(setup) == EXIT_OK
    value = json.loads(capsys.readouterr().out)
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE contacts SET deleted_at = '2026-11-25T00:00:00Z' WHERE id = 1",
        "UPDATE contacts SET email_norm = '' WHERE id = 1",
    ],
    ids=["deleted", "empty-email"],
)
def test_a_deleted_or_address_less_contact_is_not_draftable(
    setup: dict[str, Path],  # noqa: F811
    change: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _sql(setup, change)
    data = _data(setup, capsys)
    assert data["draftable"] is False
    assert data["blocked_by"] == ["no_contact_email"]


def test_an_unanswered_checklist_item_exports_as_unknown(
    setup: dict[str, Path],  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = setup["config"].read_text(encoding="utf-8")
    setup["config"].write_text(
        text
        + "review:\n"
        + "  checklists:\n"
        + "    direct_candidate:\n"
        + "      - {key: direct_signal, label: Current signal}\n"
        + "      - {key: buyer_identified, label: Buyer known}\n",
        encoding="utf-8",
    )
    _sql(
        setup,
        "UPDATE leads SET checklist = ? WHERE id = 1",
        (json.dumps({"direct_signal": "yes"}),),
    )
    data = _data(setup, capsys)
    assert data["checklist"] == {"direct_signal": "yes", "buyer_identified": "unknown"}


@pytest.mark.parametrize(
    "stored",
    ["not json [", json.dumps({"fact": "x"}), json.dumps("a string")],
    ids=["invalid-json", "object", "string"],
)
def test_unreadable_verified_facts_export_as_an_empty_list(
    setup: dict[str, Path],  # noqa: F811
    stored: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _sql(setup, "UPDATE leads SET verified_facts = ? WHERE id = 1", (stored,))
    assert _data(setup, capsys)["verified_facts"] == []


def test_evidence_is_newest_first_with_published_at(
    setup: dict[str, Path],  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The fixture's evidence was observed 2026-11-20; add an older and a newer observation.
    for url, observed, published in [
        ("https://firm.example.com/old", "2026-11-10", "2026-11-01"),
        ("https://firm.example.com/new", "2026-11-28", "2026-11-27"),
    ]:
        _sql(
            setup,
            "INSERT INTO evidence (lead_id, url, observed_at, published_at, kind)"
            " VALUES (1, ?, ?, ?, 'fact')",
            (url, observed, published),
        )
    evidence = _data(setup, capsys)["evidence"]
    assert isinstance(evidence, list)
    assert [item["observed_at"] for item in evidence] == ["2026-11-28", "2026-11-20", "2026-11-10"]
    assert [item["published_at"] for item in evidence] == ["2026-11-27", None, "2026-11-01"]
    assert evidence[0]["url"] == "https://firm.example.com/new"


def test_the_organization_exports_its_name_and_domain(
    setup: dict[str, Path],  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _data(setup, capsys)["organization"] == {
        "name": "Firm (TEST)",
        "domain": "firm.example.com",
    }
