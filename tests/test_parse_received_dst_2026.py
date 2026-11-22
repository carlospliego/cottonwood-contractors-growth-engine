# sir-target: tests/test_parse_received_dst_2026.py
"""parse_received at the 2026 Denver daylight-saving edges (F-testing-6).

Fall back, 2026-11-01: 01:00-01:59 happens twice; the first occurrence (fold=0, MDT, UTC-6)
is the one stored. Spring forward, 2026-03-08: 02:00-02:59 never happens; the chosen
behavior is to reject it (CCGE-033) rather than let zoneinfo shift it an hour.
"""

from __future__ import annotations

import pytest

from cottonwood import timeutil


@pytest.mark.parametrize(
    ("local", "stored"),
    [
        ("2026-11-01 00:59", "2026-11-01T06:59:00Z"),
        ("2026-11-01 01:30", "2026-11-01T07:30:00Z"),
        ("2026-11-01 02:00", "2026-11-01T09:00:00Z"),
    ],
)
def test_fall_back_repeated_hour_takes_the_first_occurrence(local: str, stored: str) -> None:
    assert timeutil.parse_received(local) == stored


def test_the_second_occurrence_is_reachable_through_utc() -> None:
    assert timeutil.parse_received("2026-11-01T08:30:00Z") == "2026-11-01T08:30:00Z"


@pytest.mark.parametrize("local", ["2026-03-08 02:00", "2026-03-08 02:30", "2026-03-08 02:59"])
def test_spring_forward_skipped_time_is_rejected(local: str) -> None:
    with pytest.raises(ValueError, match="does not exist in America/Denver"):
        timeutil.parse_received(local)


@pytest.mark.parametrize(
    ("local", "stored"),
    [("2026-03-08 01:59", "2026-03-08T08:59:00Z"), ("2026-03-08 03:00", "2026-03-08T09:00:00Z")],
)
def test_times_either_side_of_the_gap_are_stored(local: str, stored: str) -> None:
    assert timeutil.parse_received(local) == stored
