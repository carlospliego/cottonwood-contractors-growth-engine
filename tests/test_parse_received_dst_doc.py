# sir-target: tests/test_parse_received_dst_doc.py
"""parse_received documents and enforces both DST edges: fold and spring-forward gap."""

from __future__ import annotations

import pytest

from cottonwood import timeutil

# 2027-03-14: Denver clocks jump from 02:00 MST to 03:00 MDT.
GAP_DAY = "2027-03-14"


def test_docstring_names_the_gap_and_what_happens() -> None:
    doc = " ".join((timeutil.parse_received.__doc__ or "").split())
    assert "first occurrence (fold=0)" in doc
    assert "skipped when daylight saving time starts" in doc
    assert "raises ValueError" in doc


@pytest.mark.parametrize("hhmm", ["02:00", "02:30", "02:59"])
def test_times_in_the_gap_are_refused_not_shifted(hhmm: str) -> None:
    with pytest.raises(ValueError, match="does not exist in America/Denver"):
        timeutil.parse_received(f"{GAP_DAY} {hhmm}")


@pytest.mark.parametrize(
    ("hhmm", "utc"),
    [("01:59", "2027-03-14T08:59:00Z"), ("03:00", "2027-03-14T09:00:00Z")],
)
def test_the_minutes_either_side_of_the_gap_are_accepted(hhmm: str, utc: str) -> None:
    assert timeutil.parse_received(f"{GAP_DAY} {hhmm}") == utc
