# sir-target: tests/test_inbound_budget_format.py
"""A stated budget is stored as plain decimal digits, never scientific notation."""

from __future__ import annotations

import pytest

from cottonwood import inbound


def _budget(text: str) -> str | None:
    return inbound.validate(
        inbound.RawInquiry(
            channel="form",
            received="2026-11-16 09:30",
            segment="commercial",
            name="Pat Lee",
            budget=text,
        )
    ).budget


@pytest.mark.parametrize("text", ["1e3", "1E3", "2.5e4", "1e-3"])
def test_exponent_input_is_refused_not_stored_as_1E(text: str) -> None:
    with pytest.raises(inbound.InquiryError, match="plain digits") as caught:
        _budget(text)
    assert caught.value.field == "budget"


@pytest.mark.parametrize(
    ("text", "stored"),
    [
        ("1000", "1000"),
        ("1500.50", "1500.50"),
        ("0.0000001", "0.0000001"),
        ("12000000", "12000000"),
        ("0.00", "0"),
    ],
)
def test_stored_text_is_fixed_point(text: str, stored: str) -> None:
    result = _budget(text)
    assert result is not None
    assert result == stored
    assert "e" not in result.lower()
