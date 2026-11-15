"""The review sent to the founder: inbound inquiries, tests labeled and left out of counts.

Covers R-3 and R-31 for the inbound section. The direct-candidate and relationship-prospect
queues (R-13) are added by a later feature.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from cottonwood import inbound, timeutil

# SQL condition for leads that count. Test inquiries are listed but never counted (R-3);
# the report reuses this so both outputs agree on what a test is.
COUNTED_LEADS_FILTER = "is_test = 0"

EMPTY = "—"
TEST_LABEL = "TEST"

COLUMNS = (
    "Lead",
    "Received",
    "Channel",
    "Segment",
    "Stage",
    "Name",
    "Email",
    "Phone",
    "Company",
    "Location",
    "Scope",
    "Budget",
    "Label",
)


@dataclass(frozen=True)
class InboundCounts:
    """Non-test inquiries by channel and segment, plus how many tests were left out."""

    total: int
    by_channel: dict[str, int]
    by_segment: dict[str, int]
    tests_excluded: int


def inbound_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every inbound inquiry with its contact and organization, newest received first."""
    return conn.execute(
        "SELECT leads.id, leads.received_at, leads.channel, leads.segment, leads.stage,"
        " leads.property_location, leads.project_scope, leads.value_amount, leads.is_test,"
        " contacts.name, contacts.email, contacts.phone_e164,"
        " organizations.name AS company"
        " FROM leads"
        " LEFT JOIN contacts ON contacts.id = leads.contact_id"
        " LEFT JOIN organizations ON organizations.id = leads.organization_id"
        " WHERE leads.type = 'inbound_inquiry'"
        " ORDER BY leads.received_at IS NULL, leads.received_at DESC, leads.id DESC"
    ).fetchall()


def inbound_counts(conn: sqlite3.Connection) -> InboundCounts:
    """Count non-test inquiries by channel and segment; every known key starts at 0."""
    by_channel = dict.fromkeys(inbound.CHANNELS, 0)
    by_segment = dict.fromkeys(inbound.SEGMENTS, 0)
    total = 0
    for row in conn.execute(
        "SELECT channel, segment FROM leads"
        f" WHERE type = 'inbound_inquiry' AND {COUNTED_LEADS_FILTER}"
    ):
        total += 1
        if row[0] in by_channel:
            by_channel[row[0]] += 1
        if row[1] in by_segment:
            by_segment[row[1]] += 1
    tests = conn.execute(
        "SELECT count(*) FROM leads"
        f" WHERE type = 'inbound_inquiry' AND NOT ({COUNTED_LEADS_FILTER})"
    ).fetchone()[0]
    return InboundCounts(total, by_channel, by_segment, int(tests))


def _cell(value: object) -> str:
    """One Markdown table cell: '—' when empty, pipes and backslashes escaped, one line."""
    if value is None:
        return EMPTY
    text = str(value).strip()
    if not text:
        return EMPTY
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    return " ".join(text.splitlines())


def _received(value: object) -> str:
    """The received time in America/Denver, or '—' when it is missing."""
    if value is None:
        return EMPTY
    return timeutil.display_local(str(value))


def _count_line(counts: InboundCounts) -> str:
    channels = ", ".join(f"{k} {v}" for k, v in counts.by_channel.items())
    segments = ", ".join(f"{k} {v}" for k, v in counts.by_segment.items())
    return (
        f"Inquiries: {counts.total} ({channels}; {segments})."
        f" Test inquiries excluded: {counts.tests_excluded}."
    )


def render_review(conn: sqlite3.Connection, generated_at: str) -> str:
    """The review as Markdown, ending in a single newline."""
    lines = [
        "# Review",
        "",
        f"Generated: {timeutil.display_local(generated_at)}",
        "",
        "## Inbound inquiries",
        "",
        _count_line(inbound_counts(conn)),
        "",
    ]
    rows = inbound_rows(conn)
    if not rows:
        lines.append("No inbound inquiries logged.")
    else:
        lines.append("| " + " | ".join(COLUMNS) + " |")
        lines.append("|" + "---|" * len(COLUMNS))
        for row in rows:
            cells = [
                str(row["id"]),
                _received(row["received_at"]),
                _cell(row["channel"]),
                _cell(row["segment"]),
                _cell(row["stage"]),
                _cell(row["name"]),
                _cell(row["email"]),
                _cell(row["phone_e164"]),
                _cell(row["company"]),
                _cell(row["property_location"]),
                _cell(row["project_scope"]),
                _cell(row["value_amount"]),
                TEST_LABEL if row["is_test"] else "",
            ]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
