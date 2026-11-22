"""Time helpers: store UTC ISO-8601 strings, display in America/Denver (R-32)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

DENVER = ZoneInfo("America/Denver")

_UTC_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]00:00)$")
_LOCAL_MINUTE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


def to_utc_iso(moment: datetime) -> str:
    """Return ``moment`` as UTC ISO-8601 with second precision, e.g. 2026-01-15T19:00:00Z."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"datetime must be timezone-aware: {moment!r}")
    # isoformat, not strftime("%Y"): glibc's %Y does not zero-pad years below 1000, so
    # strftime gives '1-01-01...' on Linux where macOS gives '0001-01-01...'.
    utc = moment.astimezone(UTC).replace(microsecond=0, tzinfo=None)
    return utc.isoformat() + "Z"


def utc_now() -> str:
    """Return the current time as a UTC ISO-8601 string with second precision."""
    return to_utc_iso(datetime.now(UTC))


def parse_utc(value: str) -> datetime:
    """Parse a stored UTC ISO-8601 string (ending in Z or +00:00) into an aware datetime."""
    if not _UTC_ISO.match(value):
        raise ValueError(f"not a UTC ISO-8601 timestamp: {value!r}")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def parse_received(value: str) -> str:
    """Turn operator input into a stored UTC string.

    Accepts America/Denver local time as ``YYYY-MM-DD HH:MM`` or a UTC ISO-8601 timestamp
    ending in Z or +00:00. A local time repeated at the end of daylight saving time takes its
    first occurrence (fold=0); give the UTC form to pick the other one. A local time skipped
    when daylight saving time starts does not exist and raises ValueError.
    """
    text = value.strip()
    if _LOCAL_MINUTE.match(text):
        try:
            naive = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError(f"not a valid local date and time: {value!r}") from None
        try:
            stored = to_utc_iso(naive.replace(tzinfo=DENVER, fold=0))
        except OverflowError:
            # Near year 1 or 9999 the offset pushes the UTC time outside datetime's range.
            raise ValueError(f"date and time is out of range: {value!r}") from None
        # A time skipped by the spring-forward change (02:00-02:59 on that Sunday) does not
        # exist in Denver; zoneinfo would quietly shift it an hour. Refuse it instead.
        if to_local(stored).replace(tzinfo=None) != naive:
            raise ValueError(
                f"{text} does not exist in America/Denver (clocks skip it when daylight saving"
                " time starts); give the UTC time instead"
            )
        return stored
    try:
        return to_utc_iso(parse_utc(text))
    except (ValueError, OverflowError):
        raise ValueError(
            f"expected 'YYYY-MM-DD HH:MM' (America/Denver) or a UTC time ending in Z: {value!r}"
        ) from None


def to_local(value: str) -> datetime:
    """Return a stored UTC string as an aware datetime in America/Denver."""
    return parse_utc(value).astimezone(DENVER)


def display_local(value: str) -> str:
    """Render a stored UTC string in America/Denver, e.g. 2026-01-15 12:00 -07:00."""
    local = to_local(value)
    return f"{local:%Y-%m-%d %H:%M} {_offset_text(local)}"


def _offset_text(moment: datetime) -> str:
    """The UTC offset as +HH:MM, with :SS only when the offset has seconds (e.g. LMT)."""
    offset = moment.utcoffset()
    if offset is None:
        raise ValueError(f"datetime must be timezone-aware: {moment!r}")
    seconds = int(offset.total_seconds())
    sign = "-" if seconds < 0 else "+"
    hours, rest = divmod(abs(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    text = f"{sign}{hours:02d}:{minutes:02d}"
    return f"{text}:{secs:02d}" if secs else text


def local_date(value: str) -> date:
    """Return the America/Denver calendar date of a stored UTC string."""
    return to_local(value).date()
