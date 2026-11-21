# sir-target: tests/test_parse_received_gap.py
"""A local time skipped at the spring-forward change is refused, not shifted (F-correctness-1)."""

from __future__ import annotations

import pytest

from cottonwood import inbound, timeutil


@pytest.mark.parametrize("skipped", ["2026-03-08 02:00", "2026-03-08 02:30", "2026-03-08 02:59"])
def test_a_time_in_the_spring_forward_gap_is_refused(skipped: str) -> None:
    with pytest.raises(ValueError, match="does not exist in America/Denver"):
        timeutil.parse_received(skipped)


def test_times_either_side_of_the_gap_still_convert() -> None:
    assert timeutil.parse_received("2026-03-08 01:59") == "2026-03-08T08:59:00Z"
    assert timeutil.parse_received("2026-03-08 03:00") == "2026-03-08T09:00:00Z"


def test_the_repeated_fall_back_hour_still_takes_its_first_occurrence() -> None:
    # 01:30 happens twice on 2026-11-01; fold=0 is the first (MDT, -06:00).
    assert timeutil.parse_received("2026-11-01 01:30") == "2026-11-01T07:30:00Z"


def test_log_inbound_reports_the_gap_as_a_received_error() -> None:
    with pytest.raises(inbound.InquiryError) as caught:
        inbound.validate(
            inbound.RawInquiry(
                channel="form",
                received="2026-03-08 02:30",
                segment="commercial",
                name="Pat Lee",
                email="pat@example.com",
            )
        )
    assert caught.value.field == "received"
