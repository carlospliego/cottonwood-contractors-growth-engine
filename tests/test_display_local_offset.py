# sir-target: tests/test_display_local_offset.py
"""display_local renders offsets as ±HH:MM, adding :SS only when present (F-correctness-8)."""

from __future__ import annotations

from cottonwood import timeutil


def test_sub_minute_offset_keeps_its_seconds() -> None:
    # America/Denver used local mean time (-06:59:56) before standard time in 1883.
    assert timeutil.display_local("1880-01-01T12:00:00Z") == "1880-01-01 05:00 -06:59:56"


def test_ordinary_offsets_are_hours_and_minutes() -> None:
    assert timeutil.display_local("2026-01-15T19:00:00Z") == "2026-01-15 12:00 -07:00"
    assert timeutil.display_local("2026-07-15T19:00:00Z") == "2026-07-15 13:00 -06:00"
