# sir-target: tests/test_normalize_phone_ascii.py
"""Regression test for F-correctness-6: non-ASCII digits must not reach the E.164 key."""

from __future__ import annotations

import pytest

from cottonwood.normalize import normalize_phone


@pytest.mark.parametrize(
    "bad",
    [
        "５５５ ５５５ ５５５５",  # fullwidth digits
        "٥٥٥٥٥٥٥٥٥٥",  # Arabic-Indic digits
        "+1 801 555 ٠١٣٤",  # ASCII mixed with Arabic-Indic digits
    ],
)
def test_non_ascii_digits_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="phone|numbers"):
        normalize_phone(bad)
