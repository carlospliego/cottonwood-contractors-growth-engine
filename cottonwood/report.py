"""The weekly report sent to the founder: R-28 metrics for a period of America/Denver dates.

Every activity metric counts through events.COUNTED_ACTIVITIES_SQL (R-17), so corrections,
voided rows and test leads (R-3) never count. The report reads the database and never writes.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from cottonwood import config, events, inbound, review, timeutil

PERIODS = {"7d": 7, "30d": 30}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Working days for the same-working-day acknowledgement target: Monday-Friday, no holidays.
_LAST_WORKING_WEEKDAY = 4

LABEL_INQUIRIES = "Inquiries"
LABEL_CHANNEL = "Channel"
LABEL_SEGMENT = "Segment"
LABEL_ACK_WITHIN = "Acknowledged within target"
LABEL_ACK_OUTSIDE = "Acknowledged outside target"
LABEL_NOT_ACKNOWLEDGED = "Not acknowledged"
LABEL_MISSED_CALLS = "Missed calls"
LABEL_RETURNED_CALLS = "Returned calls"


class ReportError(ValueError):
    """The report's period options are missing, conflicting or invalid."""


@dataclass(frozen=True)
class Period:
    """An inclusive range of America/Denver calendar dates."""

    start: date
    end: date

    def contains(self, day: date) -> bool:
        """True when ``day`` falls within the period, both ends included."""
        return self.start <= day <= self.end


def _parse_date(flag: str, value: str) -> date:
    """A YYYY-MM-DD date given to --from or --to."""
    text = value.strip()
    if not _ISO_DATE.match(text):
        raise ReportError(f"{flag} expects YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ReportError(f"{flag} is not a valid date: {value!r}") from None


def parse_period(period: str | None, from_: str | None, to: str | None, today: date) -> Period:
    """Resolve --period (ending ``today``) or the inclusive --from/--to pair into a Period."""
    if period is not None:
        if from_ is not None or to is not None:
            raise ReportError("give either --period or --from and --to, not both")
        if period not in PERIODS:
            raise ReportError(f"--period must be one of {', '.join(PERIODS)}, got {period!r}")
        return Period(today - timedelta(days=PERIODS[period] - 1), today)
    if from_ is None and to is None:
        raise ReportError("give --period 7d|30d, or --from and --to (YYYY-MM-DD)")
    if from_ is None or to is None:
        raise ReportError("--from and --to must be given together")
    start = _parse_date("--from", from_)
    end = _parse_date("--to", to)
    if start > end:
        raise ReportError(f"--from {start.isoformat()} is later than --to {end.isoformat()}")
    return Period(start, end)


def working_day(day: date) -> bool:
    """True for Monday to Friday (no holidays)."""
    return day.weekday() <= _LAST_WORKING_WEEKDAY


def ack_deadline(received: date) -> date:
    """The last Denver date an acknowledgement meets the target for an inquiry received then."""
    if working_day(received):
        return received
    day = received + timedelta(days=1)
    while not working_day(day):
        day += timedelta(days=1)
    return day


def _counted_in_period(
    conn: sqlite3.Connection, activity_type: str, period: Period
) -> list[sqlite3.Row]:
    """Counted activities of one type whose occurred_at falls on a period date in Denver."""
    return [
        row
        for row in events.counted_activities(conn, activity_type)
        if period.contains(timeutil.local_date(str(row["occurred_at"])))
    ]


@dataclass(frozen=True)
class InboundMetrics:
    """Non-test inquiries received in the period, and how they were acknowledged."""

    total: int
    by_channel: dict[str, int]
    by_segment: dict[str, int]
    ack_within: int
    ack_outside: int
    not_acknowledged: int


def _inbound(conn: sqlite3.Connection, period: Period) -> InboundMetrics:
    """Count inquiries by channel and segment and judge each against the ack target."""
    by_channel = dict.fromkeys(inbound.CHANNELS, 0)
    by_segment = dict.fromkeys(inbound.SEGMENTS, 0)
    first_ack: dict[int, str] = {}
    for row in events.counted_activities(conn, "acknowledgement"):
        lead_id = row["lead_id"]
        if lead_id is not None and int(lead_id) not in first_ack:
            first_ack[int(lead_id)] = str(row["occurred_at"])
    total = within = outside = missing = 0
    for row in conn.execute(
        "SELECT id, channel, segment, received_at FROM leads"
        f" WHERE type = 'inbound_inquiry' AND {review.COUNTED_LEADS_FILTER}"
        " AND received_at IS NOT NULL ORDER BY id"
    ):
        received = timeutil.local_date(str(row["received_at"]))
        if not period.contains(received):
            continue
        total += 1
        if row["channel"] in by_channel:
            by_channel[row["channel"]] += 1
        if row["segment"] in by_segment:
            by_segment[row["segment"]] += 1
        ack = first_ack.get(int(row["id"]))
        if ack is None:
            missing += 1
        elif timeutil.local_date(ack) <= ack_deadline(received):
            within += 1
        else:
            outside += 1
    return InboundMetrics(total, by_channel, by_segment, within, outside, missing)


@dataclass(frozen=True)
class Report:
    """Every metric the weekly report prints, computed for one period."""

    generated_at: str
    period: Period
    inbound: InboundMetrics
    missed_calls: int
    returned_calls: int


def build_report(
    conn: sqlite3.Connection, period: Period, cfg: config.Config | None, generated_at: str
) -> Report:
    """Compute the report's metrics from the database (read only)."""
    del cfg  # Report settings (cost cap, blocked sending) are read by later sections.
    return Report(
        generated_at=generated_at,
        period=period,
        inbound=_inbound(conn, period),
        missed_calls=len(_counted_in_period(conn, "missed_call", period)),
        returned_calls=len(_counted_in_period(conn, "call_returned", period)),
    )


def _line(label: str, value: object) -> str:
    """One '- Label: value' metric line."""
    return f"- {label}: {value}"


def render_report(report: Report) -> str:
    """The report as Markdown, ending in a single newline."""
    metrics = report.inbound
    lines = [
        "# Weekly report",
        "",
        f"Generated: {timeutil.display_local(report.generated_at)}",
        f"Period: {report.period.start.isoformat()} to {report.period.end.isoformat()}"
        " (America/Denver)",
        "",
        "## Inbound",
        "",
        _line(LABEL_INQUIRIES, metrics.total),
    ]
    lines += [_line(f"{LABEL_CHANNEL} {k}", v) for k, v in metrics.by_channel.items()]
    lines += [_line(f"{LABEL_SEGMENT} {k}", v) for k, v in metrics.by_segment.items()]
    lines += [
        _line(LABEL_ACK_WITHIN, metrics.ack_within),
        _line(LABEL_ACK_OUTSIDE, metrics.ack_outside),
        _line(LABEL_NOT_ACKNOWLEDGED, metrics.not_acknowledged),
        _line(LABEL_MISSED_CALLS, report.missed_calls),
        _line(LABEL_RETURNED_CALLS, report.returned_calls),
    ]
    return "\n".join(lines) + "\n"
