"""The review sent to the founder: inbound inquiries, then the two candidate queues.

Covers R-3 and R-31 for the inbound section (tests labeled and left out of counts) and R-13
for the direct-candidate and relationship-prospect queues: checklist answers, newest evidence
and its age, next action, founder time and the standing hand-review result, in a stated order.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cottonwood import claims, config, events, evidence, hand_review, inbound, timeutil

# SQL condition for leads that count. Test inquiries are listed but never counted (R-3).
# The review counts and report.py's inbound and referral counts all use it, so every output
# agrees on what a test is. It names leads.is_test, so a query that joins another table
# with an is_test column still filters on the lead.
COUNTED_LEADS_FILTER = "leads.is_test = 0"

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
    """Non-test inquiries by channel and segment, plus how many tests were left out.

    ``by_channel`` and ``by_segment`` hold only the known values (inbound.CHANNELS and
    inbound.SEGMENTS). ``total`` counts every non-test inquiry, so a row stored with any
    other channel or segment (log-inbound cannot write one; a hand edit or an older import
    could) is in ``total`` but in neither breakdown, and the breakdowns can sum to less.
    """

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
        " WHERE leads.type = ?"
        " ORDER BY leads.received_at IS NULL, leads.received_at DESC, leads.id DESC",
        (inbound.LEAD_TYPE,),
    ).fetchall()


def inbound_counts(conn: sqlite3.Connection) -> InboundCounts:
    """Count non-test inquiries by channel and segment; every known key starts at 0.

    Values outside the known channels and segments count toward ``total`` only (see
    InboundCounts), so the breakdowns may not sum to it.
    """
    by_channel = dict.fromkeys(inbound.CHANNELS, 0)
    by_segment = dict.fromkeys(inbound.SEGMENTS, 0)
    total = 0
    for row in conn.execute(
        f"SELECT channel, segment FROM leads WHERE type = ? AND {COUNTED_LEADS_FILTER}",
        (inbound.LEAD_TYPE,),
    ):
        total += 1
        if row[0] in by_channel:
            by_channel[row[0]] += 1
        if row[1] in by_segment:
            by_segment[row[1]] += 1
    tests = conn.execute(
        f"SELECT count(*) FROM leads WHERE type = ? AND NOT ({COUNTED_LEADS_FILTER})",
        (inbound.LEAD_TYPE,),
    ).fetchone()[0]
    return InboundCounts(total, by_channel, by_segment, int(tests))


# Characters that would let inquirer-supplied text become a link, an image, emphasis, code or
# raw HTML in the founder's review; each is backslash-escaped so it shows as typed.
_MARKDOWN_ESCAPES = "\\|[]()<>!`*_"


def _cell(value: object) -> str:
    """One Markdown table cell: '—' when empty, one line, Markdown and HTML shown literally.

    Backslashes, pipes and the Markdown/HTML metacharacters in _MARKDOWN_ESCAPES are
    backslash-escaped, so a value such as ``[click](https://evil.example)`` or ``<img>``
    reaches the review as text rather than a link or markup.
    """
    if value is None:
        return EMPTY
    text = str(value).strip()
    if not text:
        return EMPTY
    text = "".join(f"\\{char}" if char in _MARKDOWN_ESCAPES else char for char in text)
    return " ".join(text.splitlines())


# Public name for other modules: the weekly report renders its tables with it, so it
# depends on no private review helper (F-maintainability-1).
table_cell = _cell


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
    (events.DIRECT_CANDIDATE, "Direct candidates", "No direct candidates."),
    (events.RELATIONSHIP_PROSPECT, "Relationship prospects", "No relationship prospects."),
)
CANDIDATE_LEADING_COLUMNS = ("Lead", "Organization", "Contact", "Reach", "Eligibility")
# How a researched lead can be reached: which contact routes are on file, never their values.
REACH_NONE = "none"
REACH_ROUTES = (("email", "email_norm"), ("phone", "phone_e164"), ("address", "address"))
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
    reach: str
    eligibility: str | None
    answers: dict[str, str]
    yes: int
    evidence_url: str | None
    evidence_date: str | None  # published date when known, else observed (evidence.newest)
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
        " contacts.eligibility, contacts.email_norm, contacts.phone_e164, contacts.address,"
        " contacts.deleted_at"
        " FROM leads"
        " LEFT JOIN contacts ON contacts.id = leads.contact_id"
        " LEFT JOIN organizations ON organizations.id = leads.organization_id"
        " WHERE leads.type = ?",
        (lead_type,),
    ).fetchall()
    rows: list[CandidateRow] = []
    for lead in leads:
        lead_id = int(lead["id"])
        newest = evidence.newest(conn, lead_id)
        standing = hand_review.standing_review(conn, lead_id)
        answers = _answers(lead["checklist"], items)
        founder_time = lead["founder_time_h"]
        rows.append(
            CandidateRow(
                lead_id=lead_id,
                organization=lead["organization"],
                contact=lead["contact"],
                reach=_reach(lead),
                eligibility=lead["eligibility"],
                answers=answers,
                yes=sum(1 for value in answers.values() if value == YES_ANSWER),
                evidence_url=newest.url if newest is not None else None,
                evidence_date=newest.date if newest is not None else None,
                next_action=lead["next_action"],
                founder_time_h=float(founder_time) if founder_time is not None else None,
                hand_review=(
                    hand_review.review_result(standing) or None if standing is not None else None
                ),
                is_test=bool(lead["is_test"]),
            )
        )
    return sorted(rows, key=CandidateRow.order_key)


def _reach(lead: sqlite3.Row) -> str:
    """The contact routes on file (email, phone, address), or 'none'; a deleted contact has none."""
    if lead["deleted_at"] is not None:
        return REACH_NONE
    routes = [name for name, column in REACH_ROUTES if lead[column]]
    return ", ".join(routes) or REACH_NONE


def _evidence_age(observed: str | None, today: date, max_age: int | None) -> str:
    """Days from the evidence's effective date to today in Denver, flagged when over the max."""
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
            row.reach,
            _cell(row.eligibility),
            *(row.answers[item.key] for item in items),
            str(row.yes),
            _cell(row.evidence_url),
            _evidence_age(row.evidence_date, today, max_age),
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


# Why a lead export is not draftable (R-20): no address to write to, or a suppressed one.
BLOCKED_NO_CONTACT_EMAIL = "no_contact_email"
BLOCKED_SUPPRESSED = "suppressed"
# Where prepare-outreach writes LEAD-N drafts, relative to the folder cottonwood runs from.
DRAFTS_DIR = Path("out") / "drafts"


class LeadExportError(ValueError):
    """The lead cannot be exported; ``field`` names what is wrong."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


def lead_export(
    conn: sqlite3.Connection,
    lead_id: int,
    settings: config.Config,
    library: tuple[claims.Claim, ...],
    drafts_dir: Path = DRAFTS_DIR,
) -> dict[str, object]:
    """Everything the drafting skill may use about one lead, and never an email address.

    The contact's address decides ``draftable`` but is not exported: the skill writes the
    message body and the founder addresses it in their own client (R-20, R-27, R-35).
    ``next_draft`` is the draft number the skill writes next, so a later run never
    overwrites an earlier draft the skill itself cannot see.
    """
    lead = conn.execute(
        "SELECT leads.id, leads.type, leads.stage, leads.contact_id, leads.hypothesis,"
        " leads.verified_facts, leads.checklist, organizations.name AS organization,"
        " organizations.domain_norm AS domain"
        " FROM leads LEFT JOIN organizations ON organizations.id = leads.organization_id"
        " WHERE leads.id = ?",
        (lead_id,),
    ).fetchone()
    if lead is None:
        raise LeadExportError("lead", f"no lead {lead_id}")
    contact, blocked_by = _export_contact(conn, lead["contact_id"])
    items = settings.review.checklists.get(str(lead["type"]), ())
    statuses = {status.id: status.status for status in claims.effective_statuses(conn, library)}
    sending = settings.sending
    return {
        "lead_id": int(lead["id"]),
        "type": lead["type"],
        "stage": lead["stage"],
        "organization": (
            {"name": lead["organization"], "domain": lead["domain"]}
            if lead["organization"] is not None
            else None
        ),
        "contact": contact,
        "verified_facts": _facts(lead["verified_facts"]),
        "hypothesis": lead["hypothesis"] or "",
        "evidence": _export_evidence(conn, lead_id),
        "checklist": _answers(lead["checklist"], items),
        "claims": [
            {"id": claim.id, "text": claim.text, "status": statuses.get(claim.id, claim.status)}
            for claim in library
        ],
        "sending": {
            "sender_identity": sending.sender_identity,
            "postal_address": sending.postal_address,
            "opt_out_line": sending.opt_out_line,
            "ad_identification": sending.ad_identification,
        },
        "draftable": not blocked_by,
        "blocked_by": blocked_by,
        "next_draft": next_draft_number(drafts_dir, lead_id),
    }


def next_draft_number(drafts_dir: Path, lead_id: int) -> int:
    """One more than the highest N among ``LEAD-N.md`` and ``LEAD-N.claims.json`` drafts.

    Gaps are never reused, so a removed draft's number is not handed out again.
    """
    pattern = re.compile(rf"{lead_id}-([1-9][0-9]*)(?:\.md|\.claims\.json)")
    if not drafts_dir.is_dir():
        return 1
    used = [
        int(match.group(1))
        for entry in drafts_dir.iterdir()
        if (match := pattern.fullmatch(entry.name)) is not None
    ]
    return max(used, default=0) + 1


def _export_contact(
    conn: sqlite3.Connection, contact_id: object
) -> tuple[dict[str, object] | None, list[str]]:
    """The contact without its address, and why no draft may be written for it."""
    row = None
    if contact_id is not None:
        row = conn.execute(
            "SELECT id, name, role, email_norm, eligibility, deleted_at FROM contacts WHERE id = ?",
            (contact_id,),
        ).fetchone()
    if row is None:
        return None, [BLOCKED_NO_CONTACT_EMAIL]
    blocked: list[str] = []
    suppressed = False
    if not row["email_norm"] or row["deleted_at"] is not None:
        blocked.append(BLOCKED_NO_CONTACT_EMAIL)
    else:
        suppressed = (
            conn.execute(
                "SELECT 1 FROM suppression WHERE email_norm = ?", (row["email_norm"],)
            ).fetchone()
            is not None
        )
        if suppressed:
            blocked.append(BLOCKED_SUPPRESSED)
    contact = {
        "id": int(row["id"]),
        "name": row["name"],
        "role": row["role"],
        "eligibility": row["eligibility"],
        "suppressed": suppressed,
    }
    return contact, blocked


def _export_evidence(conn: sqlite3.Connection, lead_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT url, observed_at, published_at, kind, excerpt, observation FROM evidence"
        " WHERE lead_id = ? ORDER BY observed_at DESC, id DESC",
        (lead_id,),
    )
    return [
        {
            "url": row["url"],
            "observed_at": row["observed_at"],
            "published_at": row["published_at"],
            "kind": row["kind"],
            "excerpt": row["excerpt"],
            "observation": row["observation"],
        }
        for row in rows
    ]


def _facts(stored: object) -> list[str]:
    """The stored verified facts (a JSON array of strings), or [] when absent or unreadable."""
    if not isinstance(stored, str):
        return []
    try:
        value = json.loads(stored)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
