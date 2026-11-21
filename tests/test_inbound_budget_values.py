# sir-target: tests/test_inbound_budget_values.py
"""Stated budgets: the stored text for each valid form, and exponent input refused (F-test-5).

Decision: exponent notation is rejected, not normalized, so the stored figure is the one the
inquirer typed in plain digits (CCGE-035 added the refusal, CCGE-042 the fixed-point format).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db, inbound


def _raw(budget: str) -> inbound.RawInquiry:
    return inbound.RawInquiry(
        channel="form",
        received="2026-11-16 09:30",
        segment="commercial",
        name="Pat Lee",
        budget=budget,
    )


@pytest.mark.parametrize(
    ("text", "stored"),
    [
        ("0", "0"),
        ("-0", "0"),
        ("0.00", "0"),
        ("25000.50", "25000.50"),
        ("25000", "25000"),
        (" 1500 ", "1500"),
    ],
)
def test_valid_budget_is_stored_as(text: str, stored: str) -> None:
    assert inbound.validate(_raw(text)).budget == stored


def test_exponent_notation_is_rejected_not_normalized() -> None:
    with pytest.raises(inbound.InquiryError, match="plain digits") as caught:
        inbound.validate(_raw("1e3"))
    assert caught.value.field == "budget"


def test_the_stored_text_reaches_the_lead_row(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        lead_id = inbound.log_inquiry(conn, inbound.validate(_raw("25000.50")))
        row = conn.execute(
            "SELECT value_amount, value_basis FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
    finally:
        conn.close()
    assert (str(row[0]), row[1]) == ("25000.50", inbound.BUDGET_BASIS)
