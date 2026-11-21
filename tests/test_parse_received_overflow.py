# sir-target: tests/test_parse_received_overflow.py
"""--received near year 1 or 9999 is a ValueError, not an OverflowError (F-correctness-2)."""

from __future__ import annotations

import pytest

from cottonwood import inbound, timeutil


def test_a_local_time_that_overflows_utc_is_a_value_error() -> None:
    # 23:30 on the last day of 9999 in Denver is in year 10000 in UTC.
    with pytest.raises(ValueError, match="out of range"):
        timeutil.parse_received("9999-12-31 23:30")


def test_edge_times_that_fit_still_convert() -> None:
    assert timeutil.parse_received("9999-12-31T23:59:59Z") == "9999-12-31T23:59:59Z"
    assert timeutil.parse_received("0001-01-01T00:00:00Z") == "0001-01-01T00:00:00Z"


def test_log_inbound_reports_the_overflow_as_a_received_error() -> None:
    with pytest.raises(inbound.InquiryError) as caught:
        inbound.validate(
            inbound.RawInquiry(
                channel="form",
                received="9999-12-31 23:30",
                segment="commercial",
                name="Pat Lee",
                email="pat@example.com",
            )
        )
    assert caught.value.field == "received"
