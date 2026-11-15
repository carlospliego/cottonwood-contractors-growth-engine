"""Tests for UTC storage and America/Denver display helpers."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from cottonwood import timeutil


def test_utc_now_is_second_precision_utc_iso() -> None:
    value = timeutil.utc_now()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value)


def test_to_utc_iso_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        timeutil.to_utc_iso(datetime(2026, 1, 15, 12, 0))


def test_to_utc_iso_converts_offsets_and_drops_microseconds() -> None:
    moment = datetime(2026, 1, 15, 12, 0, 5, 999_999, tzinfo=timezone(timedelta(hours=-7)))
    assert timeutil.to_utc_iso(moment) == "2026-01-15T19:00:05Z"


def test_display_local_winter_is_mst() -> None:
    shown = timeutil.display_local("2026-01-15T19:00:00Z")
    assert "12:00" in shown
    assert "-07:00" in shown
    assert shown == "2026-01-15 12:00 -07:00"


def test_display_local_summer_is_mdt() -> None:
    shown = timeutil.display_local("2026-07-15T18:00:00Z")
    assert "12:00" in shown
    assert "-06:00" in shown


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        # DST starts 2026-03-08 at 02:00 local (09:00Z): 01:59 MST is followed by 03:00 MDT.
        ("2026-03-08T08:59:00Z", "2026-03-08 01:59 -07:00"),
        ("2026-03-08T09:00:00Z", "2026-03-08 03:00 -06:00"),
        # DST ends 2026-11-01 at 02:00 local (08:00Z): 01:59 MDT is followed by 01:00 MST.
        ("2026-11-01T07:59:00Z", "2026-11-01 01:59 -06:00"),
        ("2026-11-01T08:00:00Z", "2026-11-01 01:00 -07:00"),
    ],
)
def test_display_local_across_dst_changes(stored: str, shown: str) -> None:
    assert timeutil.display_local(stored) == shown


def test_local_date_uses_denver_calendar_day() -> None:
    assert timeutil.local_date("2026-11-16T05:30:00Z") == date(2026, 11, 15)
    assert timeutil.local_date("2026-11-16T07:30:00Z") == date(2026, 11, 16)


def test_parse_utc_round_trips_and_rejects_non_utc() -> None:
    assert timeutil.parse_utc("2026-01-15T19:00:00Z") == datetime(2026, 1, 15, 19, tzinfo=UTC)
    assert timeutil.parse_utc("2026-01-15T19:00:00+00:00") == datetime(2026, 1, 15, 19, tzinfo=UTC)
    with pytest.raises(ValueError, match="not a UTC"):
        timeutil.parse_utc("2026-01-15T12:00:00-07:00")
    with pytest.raises(ValueError, match="not a UTC"):
        timeutil.parse_utc("2026-01-15")
