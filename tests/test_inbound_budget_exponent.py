# sir-target: tests/test_inbound_budget_exponent.py
"""A budget in exponent form is refused instead of stored as '1E+5' (F-correctness-3)."""

from __future__ import annotations

import pytest

from cottonwood import inbound


def _raw(budget: str) -> inbound.RawInquiry:
    return inbound.RawInquiry(
        channel="form",
        received="2026-11-16 09:30",
        segment="commercial",
        name="Pat Lee",
        email="pat@example.com",
        budget=budget,
    )


@pytest.mark.parametrize("budget", ["1e5", "1E5", "2.5e3", "1E+2", "5e-1"])
def test_exponent_form_is_refused_on_the_budget_field(budget: str) -> None:
    with pytest.raises(inbound.InquiryError, match="plain digits") as caught:
        inbound.validate(_raw(budget))
    assert caught.value.field == "budget"


@pytest.mark.parametrize(
    ("budget", "stored"), [("45000", "45000"), ("45000.50", "45000.50"), ("0", "0")]
)
def test_plain_amounts_are_still_stored_as_typed(budget: str, stored: str) -> None:
    assert inbound.validate(_raw(budget)).budget == stored
