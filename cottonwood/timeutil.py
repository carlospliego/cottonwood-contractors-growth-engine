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
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    first occurrence (fold=0); give the UTC form to pick the other one.
    """
    text = value.strip()
    if _LOCAL_MINUTE.match(text):
        try:
            naive = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError(f"not a valid local date and time: {value!r}") from None
        return to_utc_iso(naive.replace(tzinfo=DENVER, fold=0))
    try:
        return to_utc_iso(parse_utc(text))
    except ValueError:
        raise ValueError(
            f"expected 'YYYY-MM-DD HH:MM' (America/Denver) or a UTC time ending in Z: {value!r}"
        ) from None


def to_local(value: str) -> datetime:
    """Return a stored UTC string as an aware datetime in America/Denver."""
    return parse_utc(value).astimezone(DENVER)


def display_local(value: str) -> str:
    """Render a stored UTC string in America/Denver, e.g. 2026-01-15 12:00 -07:00."""
    local = to_local(value)
    offset = local.strftime("%z")
    return f"{local:%Y-%m-%d %H:%M} {offset[:3]}:{offset[3:]}"


def local_date(value: str) -> date:
    """Return the America/Denver calendar date of a stored UTC string."""
    return to_local(value).date()
