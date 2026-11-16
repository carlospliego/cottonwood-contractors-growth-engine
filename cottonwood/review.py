"""The review sent to the founder: inbound inquiries, then the two candidate queues.

Covers R-3 and R-31 for the inbound section (tests labeled and left out of counts) and R-13
for the direct-candidate and relationship-prospect queues: checklist answers, newest evidence
and its age, next action, founder time and the standing hand-review result, in a stated order.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date

from cottonwood import config, hand_review, inbound, timeutil

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


ORDER_LINE = (
    "Order: most yes answers first; ties: lower founder time first (unknown last);"
    " then lowest lead id."
)
UNKNOWN_ANSWER = "unknown"
YES_ANSWER = "yes"
SECTIONS = (
    ("direct_candidate", "Direct candidates", "No direct candidates."),
    ("relationship_prospect", "Relationship prospects", "No relationship prospects."),
)
CANDIDATE_LEADING_COLUMNS = ("Lead", "Organization", "Contact", "Eligibility")
CANDIDATE_TRAILING_COLUMNS = (
    "Yes",
    "Evidence URL",
    "Evidence age (days)",
    "Next action",
    "Founder time (h)",
    "Hand review",
    "Label",
)


@dataclass(frozen=True)
class CandidateRow:
    """One researched lead as the queue shows it."""

    lead_id: int
    organization: str | None
    contact: str | None
    eligibility: str | None
    answers: dict[str, str]
    yes: int
    evidence_url: str | None
    evidence_observed: str | None
    next_action: str | None
    founder_time_h: float | None
    hand_review: str | None
    is_test: bool

    def order_key(self) -> tuple[int, bool, float, int]:
        """Most yes first; then lower founder time, unknown last; then lowest lead id."""
        unknown = self.founder_time_h is None
        return (-self.yes, unknown, self.founder_time_h or 0.0, self.lead_id)


def _answers(stored: object, items: tuple[config.ChecklistItem, ...]) -> dict[str, str]:
    """The configured items' answers; an item with no stored answer is 'unknown'."""
    parsed: object = None
    if isinstance(stored, str):
        try:
            parsed = json.loads(stored)
        except json.JSONDecodeError:
            parsed = None
    values = parsed if isinstance(parsed, dict) else {}
    answers: dict[str, str] = {}
    for item in items:
        value = values.get(item.key)
        answers[item.key] = value if isinstance(value, str) and value else UNKNOWN_ANSWER
    return answers


def candidate_rows(
    conn: sqlite3.Connection, lead_type: str, items: tuple[config.ChecklistItem, ...]
) -> list[CandidateRow]:
    """Every lead of ``lead_type`` with its newest evidence and standing review, in queue order."""
    leads = conn.execute(
        "SELECT leads.id, leads.checklist, leads.next_action, leads.founder_time_h,"
        " leads.is_test, organizations.name AS organization, contacts.name AS contact,"
        " contacts.eligibility"
        " FROM leads"
        " LEFT JOIN contacts ON contacts.id = leads.contact_id"
        " LEFT JOIN organizations ON organizations.id = leads.organization_id"
        " WHERE leads.type = ?",
        (lead_type,),
    ).fetchall()
    rows: list[CandidateRow] = []
    for lead in leads:
        lead_id = int(lead["id"])
        evidence = conn.execute(
            "SELECT url, observed_at FROM evidence WHERE lead_id = ?"
            " ORDER BY observed_at DESC, id DESC LIMIT 1",
            (lead_id,),
        ).fetchone()
        standing = hand_review.standing_review(conn, lead_id)
        answers = _answers(lead["checklist"], items)
        founder_time = lead["founder_time_h"]
        rows.append(
            CandidateRow(
                lead_id=lead_id,
                organization=lead["organization"],
                contact=lead["contact"],
                eligibility=lead["eligibility"],
                answers=answers,
                yes=sum(1 for value in answers.values() if value == YES_ANSWER),
                evidence_url=evidence["url"] if evidence is not None else None,
                evidence_observed=evidence["observed_at"] if evidence is not None else None,
                next_action=lead["next_action"],
                founder_time_h=float(founder_time) if founder_time is not None else None,
                hand_review=(
                    hand_review.review_result(standing) or None if standing is not None else None
                ),
                is_test=bool(lead["is_test"]),
            )
        )
    return sorted(rows, key=CandidateRow.order_key)


def _evidence_age(observed: str | None, today: date, max_age: int | None) -> str:
    """Days from the evidence's observed date to today in Denver, flagged when over the max."""
    if observed is None:
        return EMPTY
    try:
        observed_day = date.fromisoformat(observed.strip()[:10])
    except ValueError:
        return EMPTY
    days = (today - observed_day).days
    if max_age is not None and days > max_age:
        return f"{days} (over {max_age})"
    return str(days)


def _hours(value: float | None) -> str:
    """Founder hours without trailing zeros (1.5, 4, 0.25), or '—' when unknown."""
    if value is None:
        return EMPTY
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _candidate_section(
    title: str,
    empty_line: str,
    rows: list[CandidateRow],
    items: tuple[config.ChecklistItem, ...],
    max_age: int | None,
    today: date,
) -> list[str]:
    """One candidate queue: order rule, max age, checklist legend, then the table."""
    age_line = (
        f"Max evidence age: {max_age} days"
        if max_age is not None
        else "Max evidence age: not configured"
    )
    lines = [f"## {title}", "", ORDER_LINE, age_line, ""]
    if items:
        lines.append("Checklist:")
        lines.extend(f"- {item.key}: {item.label}" for item in items)
        lines.append("")
    if not rows:
        lines.append(empty_line)
        return lines
    columns = (
        *CANDIDATE_LEADING_COLUMNS,
        *(item.key for item in items),
        *CANDIDATE_TRAILING_COLUMNS,
    )
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "---|" * len(columns))
    for row in rows:
        cells = [
            str(row.lead_id),
            _cell(row.organization),
            _cell(row.contact),
            _cell(row.eligibility),
            *(row.answers[item.key] for item in items),
            str(row.yes),
            _cell(row.evidence_url),
            _evidence_age(row.evidence_observed, today, max_age),
            _cell(row.next_action),
            _hours(row.founder_time_h),
            row.hand_review or EMPTY,
            TEST_LABEL if row.is_test else "",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_review(
    conn: sqlite3.Connection,
    generated_at: str,
    review_config: config.ReviewConfig | None = None,
) -> str:
    """The review as Markdown, ending in a single newline."""
    settings = review_config if review_config is not None else config.ReviewConfig()
    lines = _inbound_section(conn, generated_at)
    today = timeutil.local_date(generated_at)
    for lead_type, title, empty_line in SECTIONS:
        items = settings.checklists.get(lead_type, ())
        lines.append("")
        lines.extend(
            _candidate_section(
                title,
                empty_line,
                candidate_rows(conn, lead_type, items),
                items,
                settings.max_evidence_age_days,
                today,
            )
        )
    return "\n".join(lines) + "\n"


def _inbound_section(conn: sqlite3.Connection, generated_at: str) -> list[str]:
    """The title, generated time and inbound inquiries, as before the candidate queues."""
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
    return lines
