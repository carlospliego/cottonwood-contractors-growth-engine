"""The weekly report sent to the founder: R-28 metrics for a period of America/Denver dates.

Every activity metric counts through events.COUNTED_ACTIVITIES_SQL (R-17), so corrections,
voided rows and test leads (R-3) never count. The report reads the database and never writes.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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
LABEL_QUALIFIED = "Qualified direct conversations"
LABEL_PARTNER = "Partner conversations"
LABEL_REMOTE_SCREENS = "Remote screens"
LABEL_WALKTHROUGHS = "Walkthroughs"
LABEL_PROPOSALS = "Proposals"
LABEL_WON = "Won projects"
LABEL_KPI = "KPI (qualified + partner) per founder hour"
LABEL_FOUNDER_HOURS = "Founder hours"
LABEL_FOUNDER_OBSERVED = "Founder hours observed"
LABEL_FOUNDER_ESTIMATED = "Founder hours estimated"
LABEL_DEVELOPER_HOURS = "Developer hours"

# Outcome events counted per type (R-28), in the order the report prints them.
OUTCOME_LABELS = {
    "partner_conversation": LABEL_PARTNER,
    "remote_screen": LABEL_REMOTE_SCREENS,
    "walkthrough": LABEL_WALKTHROUGHS,
    "proposal": LABEL_PROPOSALS,
    "won": LABEL_WON,
}
FOUNDER = "founder"
DEVELOPER = "developer"
NOT_APPLICABLE = "n/a"
_KPI_PLACES = Decimal("0.01")
_MONEY_PLACES = Decimal("0.01")

LABEL_MODEL_COST = "Model cost"
LABEL_MODEL_OBSERVED = "Model cost observed"
LABEL_MODEL_ESTIMATED = "Model cost estimated"
LABEL_MODEL_MTD = "Model cost month to date"
LABEL_OTHER_COSTS = "Other costs"
LABEL_OTHER_OBSERVED = "Other costs observed"
LABEL_OTHER_ESTIMATED = "Other costs estimated"
NO_CAP = "No model-cost cap configured (report.model_cost_cap_usd)."
COST_COLUMNS = ("Category", "Amount (USD)")
SENDING_BLOCKED_HEADING = "## Sending blocked"
SENDING_BLOCKED_INTRO = "Sending is blocked until this open question is answered:"

LABEL_RESEARCHED_DIRECT = "Researched direct candidates"
LABEL_RESEARCHED_PARTNERS = "Researched partner firms"
LABEL_HAND_REVIEW = "Hand review"
LABEL_APPROVALS = "Approvals"
LABEL_DRAFTS = "Prepared drafts"
LABEL_SENDS = "Sends"
LABEL_GATE_VIOLATIONS = "Gate violations"
LABEL_REPLIES = "Replies"
LABEL_OPT_OUTS = "Opt-outs"
LABEL_DATA_QUALITY = "Data-quality failures"
LABEL_REFERRED = "Referred leads"
TOTAL = "total"

# The two outreach motions (lead types) that research and hand review are counted by (R-11).
DIRECT_MOTION = "direct_candidate"
PARTNER_MOTION = "relationship_prospect"
MOTIONS = (DIRECT_MOTION, PARTNER_MOTION)
# Payload contract for activities later features write (build assumption 4).
RESULT_KEY = "result"
REPLY_TYPE_KEY = "reply_type"
HAND_REVIEW_RESULTS = ("relevant", "irrelevant", "fabricated")
FABRICATED = "fabricated"
REPLY_TYPES = ("interested", "not_now", "not_relevant", "referral", "opt_out", "bounce", "other")
OTHER_REPLY = "other"
OPT_OUT_REPLY = "opt_out"
# Outreach steps counted per activity type, in the order the report prints them.
OUTREACH_LABELS = {
    "approval": LABEL_APPROVALS,
    "draft_prepared": LABEL_DRAFTS,
    "sent": LABEL_SENDS,
    "gate_violation": LABEL_GATE_VIOLATIONS,
}
REFERRAL_COLUMNS = ("Partner lead", "Name", "Referred leads")


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


def _qualified(conn: sqlite3.Connection, period: Period) -> int:
    """Distinct leads with a counted stage change into buyer_need_confirmed in the period (R-16).

    Nothing else qualifies a lead: inquiries, imports and notes never do, and voided moves and
    correction reverts are already left out by COUNTED_ACTIVITIES_SQL.
    """
    leads = {
        int(row["lead_id"])
        for row in _counted_in_period(conn, "stage_change", period)
        if row["lead_id"] is not None
        and json.loads(str(row["payload"])).get("to") == events.QUALIFIED_STAGE
    }
    return len(leads)


@dataclass(frozen=True)
class HoursMetrics:
    """Counted hours in the period: founder total split observed vs estimated, and developer."""

    founder_total: Decimal
    founder_observed: Decimal
    founder_estimated: Decimal
    developer: Decimal


def _hours(conn: sqlite3.Connection, period: Period) -> HoursMetrics:
    """Founder and developer hours from the counted time entries dated in the period."""
    totals = events.time_totals(conn, period.start, period.end)
    observed = estimated = Decimal(0)
    # The same entries time_totals sums, so the founder split always adds up to its total.
    for payload in events.entries_in_range(conn, events.TIME_KIND, period.start, period.end):
        if payload["person"] != FOUNDER:
            continue
        hours = Decimal(str(payload["hours"]))
        if payload["estimated"] is True:
            estimated += hours
        else:
            observed += hours
    return HoursMetrics(
        founder_total=totals.by_person.get(FOUNDER, Decimal(0)),
        founder_observed=observed,
        founder_estimated=estimated,
        developer=totals.by_person.get(DEVELOPER, Decimal(0)),
    )


def kpi(qualified: int, partner: int, founder_hours: Decimal) -> Decimal | None:
    """(qualified + partner) / founder hours to 2 places; None when there are no founder hours."""
    if founder_hours == 0:
        return None
    return (Decimal(qualified + partner) / founder_hours).quantize(_KPI_PLACES, ROUND_HALF_UP)


def _payload(row: sqlite3.Row) -> dict[str, object]:
    """An activity row's JSON payload as a dict (empty when it is not an object)."""
    value = json.loads(str(row["payload"]))
    return value if isinstance(value, dict) else {}


def _imported_in_period(conn: sqlite3.Connection, period: Period) -> list[sqlite3.Row]:
    """Counted imported activities in the period that first brought a lead in.

    A matched re-import that only added evidence records created=false; it is not a new
    research or referral arrival, so it is left out.
    """
    return [
        row
        for row in _counted_in_period(conn, "imported", period)
        if _payload(row).get("created") is not False
    ]


def _lead_types(conn: sqlite3.Connection) -> dict[int, str]:
    """Every lead's type by id."""
    return {int(row["id"]): str(row["type"]) for row in conn.execute("SELECT id, type FROM leads")}


@dataclass(frozen=True)
class FunnelMetrics:
    """Research, hand review, outreach steps, replies, opt-outs and data quality (R-28)."""

    researched: dict[str, int]
    hand_review: dict[str, dict[str, int]]
    hand_review_totals: dict[str, int]
    outreach: dict[str, int]
    replies: dict[str, int]
    opt_outs: int
    data_quality_failures: int


def _funnel(conn: sqlite3.Connection, period: Period) -> FunnelMetrics:
    """Count the outreach funnel from counted activities in the period; every key starts at 0."""
    types = _lead_types(conn)
    researched_leads: dict[str, set[int]] = {motion: set() for motion in MOTIONS}
    for row in _imported_in_period(conn, period):
        lead_id = row["lead_id"]
        if lead_id is not None and types.get(int(lead_id)) in researched_leads:
            researched_leads[types[int(lead_id)]].add(int(lead_id))
    hand_review = {motion: dict.fromkeys(HAND_REVIEW_RESULTS, 0) for motion in MOTIONS}
    hand_review_totals = dict.fromkeys(MOTIONS, 0)
    fabricated = 0
    for row in _counted_in_period(conn, "hand_review", period):
        result = _payload(row).get(RESULT_KEY)
        if result == FABRICATED:
            fabricated += 1
        lead_id = row["lead_id"]
        motion = types.get(int(lead_id)) if lead_id is not None else None
        if motion not in hand_review_totals:
            continue
        hand_review_totals[motion] += 1
        if isinstance(result, str) and result in hand_review[motion]:
            hand_review[motion][result] += 1
    replies = dict.fromkeys(REPLY_TYPES, 0)
    for row in _counted_in_period(conn, "reply", period):
        reply_type = _payload(row).get(REPLY_TYPE_KEY)
        key = reply_type if isinstance(reply_type, str) and reply_type in replies else OTHER_REPLY
        replies[key] += 1
    suppressed = len(_counted_in_period(conn, "suppressed", period))
    rejected = len(_counted_in_period(conn, "import_rejected", period))
    return FunnelMetrics(
        researched={motion: len(leads) for motion, leads in researched_leads.items()},
        hand_review=hand_review,
        hand_review_totals=hand_review_totals,
        outreach={kind: len(_counted_in_period(conn, kind, period)) for kind in OUTREACH_LABELS},
        replies=replies,
        opt_outs=replies[OPT_OUT_REPLY] + suppressed,
        data_quality_failures=rejected + fabricated,
    )


@dataclass(frozen=True)
class Referral:
    """One referring partner lead and how many referred leads arrived in the period."""

    partner_id: int
    name: str | None
    count: int


def _referrals(conn: sqlite3.Connection, period: Period) -> list[Referral]:
    """Referred non-test leads with an imported or inquiry_logged activity in the period (R-12).

    Each referred lead counts once, grouped by the partner lead it names in referred_by.
    """
    rows = _imported_in_period(conn, period) + _counted_in_period(conn, "inquiry_logged", period)
    arrived = {int(row["lead_id"]) for row in rows if row["lead_id"] is not None}
    counts: dict[int, int] = {}
    for row in conn.execute(
        "SELECT id, referred_by FROM leads"
        f" WHERE referred_by IS NOT NULL AND {review.COUNTED_LEADS_FILTER}"
    ):
        if int(row["id"]) in arrived:
            partner = int(row["referred_by"])
            counts[partner] = counts.get(partner, 0) + 1
    referrals = []
    for partner_id in sorted(counts):
        name_row = conn.execute(
            "SELECT organizations.name AS org, contacts.name AS contact FROM leads"
            " LEFT JOIN organizations ON organizations.id = leads.organization_id"
            " LEFT JOIN contacts ON contacts.id = leads.contact_id"
            " WHERE leads.id = ?",
            (partner_id,),
        ).fetchone()
        name = None
        if name_row is not None:
            for candidate in (name_row["org"], name_row["contact"]):
                if candidate is not None and str(candidate).strip():
                    name = str(candidate).strip()
                    break
        referrals.append(Referral(partner_id, name, counts[partner_id]))
    return referrals


@dataclass(frozen=True)
class ModelCostMetrics:
    """Model cost of agent runs in the period, observed vs estimated, and month to date."""

    total: Decimal
    observed: Decimal
    estimated: Decimal
    month_to_date: Decimal
    cap: Decimal | None


def _run_costs(conn: sqlite3.Connection) -> list[tuple[date, Decimal, bool]]:
    """(Denver start date, cost, estimated) for every agent run with a readable cost_usd.

    A NULL or non-decimal cost_usd is skipped; cost_estimated 1 is estimated, 0 or NULL observed.
    """
    runs = []
    for row in conn.execute("SELECT started_at, cost_usd, cost_estimated FROM agent_runs"):
        if row["cost_usd"] is None:
            continue
        try:
            cost = Decimal(str(row["cost_usd"]).strip())
        except InvalidOperation:
            continue
        if not cost.is_finite():
            continue
        started = timeutil.local_date(str(row["started_at"]))
        runs.append((started, cost, row["cost_estimated"] == 1))
    return runs


def _model_cost(conn: sqlite3.Connection, period: Period, cap: Decimal | None) -> ModelCostMetrics:
    """Sum agent run costs started in the period, and in the end date's Denver month to date."""
    observed = estimated = month_to_date = Decimal(0)
    month_start = period.end.replace(day=1)
    for started, cost, is_estimated in _run_costs(conn):
        if period.contains(started):
            if is_estimated:
                estimated += cost
            else:
                observed += cost
        if month_start <= started <= period.end:
            month_to_date += cost
    return ModelCostMetrics(observed + estimated, observed, estimated, month_to_date, cap)


@dataclass(frozen=True)
class Report:
    """Every metric the weekly report prints, computed for one period."""

    generated_at: str
    period: Period
    inbound: InboundMetrics
    missed_calls: int
    returned_calls: int
    qualified: int
    outcomes: dict[str, int]
    hours: HoursMetrics
    kpi: Decimal | None
    funnel: FunnelMetrics
    referrals: list[Referral]
    model_cost: ModelCostMetrics
    other_costs: events.CostTotals
    sending_blocked_by: str | None


def build_report(
    conn: sqlite3.Connection, period: Period, cfg: config.Config | None, generated_at: str
) -> Report:
    """Compute the report's metrics from the database (read only).

    ``cfg`` supplies the model-cost cap and the blocked-sending question; None means neither.
    """
    qualified = _qualified(conn, period)
    outcomes = {kind: len(_counted_in_period(conn, kind, period)) for kind in OUTCOME_LABELS}
    hours = _hours(conn, period)
    return Report(
        generated_at=generated_at,
        period=period,
        inbound=_inbound(conn, period),
        missed_calls=len(_counted_in_period(conn, "missed_call", period)),
        returned_calls=len(_counted_in_period(conn, "call_returned", period)),
        qualified=qualified,
        outcomes=outcomes,
        hours=hours,
        kpi=kpi(qualified, outcomes["partner_conversation"], hours.founder_total),
        funnel=_funnel(conn, period),
        referrals=_referrals(conn, period),
        model_cost=_model_cost(conn, period, cfg.model_cost_cap_usd if cfg else None),
        other_costs=events.cost_totals(conn, period.start, period.end),
        sending_blocked_by=cfg.sending_blocked_by if cfg else None,
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
        "",
        "## Conversations and KPI",
        "",
        _line(LABEL_QUALIFIED, report.qualified),
    ]
    lines += [_line(OUTCOME_LABELS[k], v) for k, v in report.outcomes.items()]
    lines.append(_line(LABEL_KPI, NOT_APPLICABLE if report.kpi is None else report.kpi))
    hours = report.hours
    lines += [
        "",
        "## Hours",
        "",
        _line(LABEL_FOUNDER_HOURS, hours.founder_total),
        _line(LABEL_FOUNDER_OBSERVED, hours.founder_observed),
        _line(LABEL_FOUNDER_ESTIMATED, hours.founder_estimated),
        _line(LABEL_DEVELOPER_HOURS, hours.developer),
    ]
    lines += _render_funnel(report.funnel)
    lines += _render_referrals(report.referrals)
    lines += _render_costs(report.model_cost, report.other_costs)
    lines += _render_blocked(report.sending_blocked_by)
    return "\n".join(lines) + "\n"


def money(value: Decimal) -> str:
    """A USD amount to 2 places for display (sums stay exact), e.g. 1.75 or 100.00."""
    return f"{value.quantize(_MONEY_PLACES, ROUND_HALF_UP):f}"


def _mtd_value(model: ModelCostMetrics) -> str:
    """Month-to-date model cost, against the cap when one is configured."""
    if model.cap is None:
        return money(model.month_to_date)
    left = model.cap - model.month_to_date
    status = f"{money(left)} remaining" if left >= 0 else f"{money(-left)} over cap"
    return f"{money(model.month_to_date)} of {money(model.cap)} ({status})"


def _render_costs(model: ModelCostMetrics, other: events.CostTotals) -> list[str]:
    """The costs section: model cost (observed vs estimated, month to date) and other costs."""
    lines = [
        "",
        "## Costs",
        "",
        _line(LABEL_MODEL_COST, money(model.total)),
        _line(LABEL_MODEL_OBSERVED, money(model.observed)),
        _line(LABEL_MODEL_ESTIMATED, money(model.estimated)),
        _line(LABEL_MODEL_MTD, _mtd_value(model)),
    ]
    if model.cap is None:
        lines.append(NO_CAP)
    lines += [
        _line(LABEL_OTHER_COSTS, money(other.total)),
        _line(LABEL_OTHER_OBSERVED, money(other.observed)),
        _line(LABEL_OTHER_ESTIMATED, money(other.estimated)),
    ]
    if other.by_category:
        lines += ["", "| " + " | ".join(COST_COLUMNS) + " |", "|" + "---|" * len(COST_COLUMNS)]
        for category in sorted(other.by_category):
            amount = money(other.by_category[category])
            lines.append(f"| {review.table_cell(category)} | {amount} |")
    return lines


def _render_blocked(question: str | None) -> list[str]:
    """The blocked-sending section quoting the open question, or nothing when none is set."""
    if question is None:
        return []
    lines = ["", SENDING_BLOCKED_HEADING, "", SENDING_BLOCKED_INTRO, ""]
    lines += [f"> {line}".rstrip() for line in question.splitlines()]
    return lines


def _render_funnel(funnel: FunnelMetrics) -> list[str]:
    """The prospecting/outreach, replies/opt-outs and data-quality sections."""
    lines = [
        "",
        "## Prospecting and outreach",
        "",
        _line(LABEL_RESEARCHED_DIRECT, funnel.researched[DIRECT_MOTION]),
        _line(LABEL_RESEARCHED_PARTNERS, funnel.researched[PARTNER_MOTION]),
    ]
    for motion in MOTIONS:
        lines += [
            _line(f"{LABEL_HAND_REVIEW} {motion} {result}", count)
            for result, count in funnel.hand_review[motion].items()
        ]
        lines.append(
            _line(f"{LABEL_HAND_REVIEW} {motion} {TOTAL}", funnel.hand_review_totals[motion])
        )
    lines += [_line(OUTREACH_LABELS[k], v) for k, v in funnel.outreach.items()]
    lines += ["", "## Replies and opt-outs", ""]
    lines += [_line(f"{LABEL_REPLIES} {k}", v) for k, v in funnel.replies.items()]
    lines.append(_line(LABEL_OPT_OUTS, funnel.opt_outs))
    lines += ["", "## Data quality", "", _line(LABEL_DATA_QUALITY, funnel.data_quality_failures)]
    return lines


def _render_referrals(referrals: list[Referral]) -> list[str]:
    """The referrals section: one table row per referring partner, then the total."""
    lines = ["", "## Referrals", ""]
    if referrals:
        lines.append("| " + " | ".join(REFERRAL_COLUMNS) + " |")
        lines.append("|" + "---|" * len(REFERRAL_COLUMNS))
        for referral in referrals:
            cells = [
                str(referral.partner_id),
                review.table_cell(referral.name),
                str(referral.count),
            ]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    lines.append(_line(LABEL_REFERRED, sum(r.count for r in referrals)))
    return lines
