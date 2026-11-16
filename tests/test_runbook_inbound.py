"""The runbook's inbound verification checklist and relay sections (R-4, relay decision)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = REPO_ROOT / "docs" / "runbook.md"

CHECKLIST_ITEMS = (
    "commercial test submission",
    "residential test submission",
    "spam/blocked-submission path",
    "notification spam-folder check",
    "Formspark account owner, plan, limits and submission retention",
    "Auto-forward to the developer",
    "Mobile form and phone-link check",
    "Missed-call handling and owner",
    "Same-working-day response capacity",
    "GA4 vs privacy-page reconciliation",
)


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def _section(title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", _text(), re.M | re.S)
    assert match, f"runbook has no '## {title}' section"
    return match.group(1)


def _checklist_rows() -> list[list[str]]:
    rows = [
        line
        for line in _section("Inbound verification checklist").splitlines()
        if line.startswith("|")
    ]
    return [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows]


def test_checklist_table_has_the_three_fields() -> None:
    header = _checklist_rows()[0]
    assert header == ["Item", "checked_at", "result", "owner"]


@pytest.mark.parametrize("item", CHECKLIST_ITEMS)
def test_each_r4_item_has_its_own_row_with_three_fields(item: str) -> None:
    rows = [row for row in _checklist_rows()[2:] if item.lower() in row[0].lower()]
    assert len(rows) == 1, f"expected one checklist row for {item!r}"
    assert len(rows[0]) == 4


def test_checklist_has_exactly_one_row_per_item() -> None:
    assert len(_checklist_rows()[2:]) == len(CHECKLIST_ITEMS)


def test_relay_states_forwarding_daily_note_and_same_day_logging() -> None:
    relay = " ".join(_section("Relay").split())
    assert "Formspark notifications and replies to the outreach mailbox are auto-forwarded" in relay
    assert "(or CC'd) to the developer" in relay
    assert "daily note covering calls" in relay
    assert "in-person events" in relay
    assert "logged the same working day" in relay
    assert "opt-outs the same day" in relay


def test_relay_has_form_and_phone_examples_and_test_flag() -> None:
    relay = _section("Relay")
    assert "cottonwood log-inbound --channel form" in relay
    assert "cottonwood log-inbound --channel phone" in relay
    assert "--test" in relay
    assert "--test" in _section("Inbound verification checklist")


def test_placeholder_line_is_gone_and_sections_keep_their_order() -> None:
    text = _text()
    assert "Later features add the inbound checklist and relay sections" not in text
    headings = re.findall(r"^## (.+)$", text, re.M)
    assert headings == [
        "Restore from backup",
        "Re-applying suppression after a restore",
        "Deletion requests",
        "Inbound verification checklist",
        "Relay",
        "Research run",
    ]
