"""Lead events, corrections, and founder time and cost entries (R-15, R-17, R-30)."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import NamedTuple
from urllib.parse import urlparse

from cottonwood import timeutil

# R-15, in the spec's order.
EVENT_TYPES = (
    "acknowledgement",
    "call",
    "missed_call",
    "call_returned",
    "remote_screen",
    "walkthrough",
    "proposal",
    "won",
    "lost",
    "partner_conversation",
    "handoff",
    "note",
)
DEFAULT_ACTOR = "developer"

# R-14: direct and inbound leads share one list; relationship prospects have their own.
DIRECT_STAGES = (
    "candidate",
    "researched",
    "contacted_or_replied",
    "buyer_need_confirmed",
    "walkthrough",
    "proposal",
    "won",
    "lost",
    "closed_no_fit",
)
RELATIONSHIP_STAGES = (
    "identified",
    "researched",
    "introduced",
    "responded",
    "active_relationship",
    "closed_no_fit",
)
STAGES_BY_LEAD_TYPE = {
    "inbound_inquiry": DIRECT_STAGES,
    "direct_candidate": DIRECT_STAGES,
    "relationship_prospect": RELATIONSHIP_STAGES,
}
# R-16: the only way into this stage is an event stating the need or a procurement URL.
QUALIFIED_STAGE = "buyer_need_confirmed"

# The stage_change payload key naming the activity that CAUSED the move (AC-4.3). Despite the
# name it is not always an R-15 event: log_event writes the event's id, but log_correction
# writes the correction's id for a revert. Tell the two apart by the type of the row it names
# (see is_revert / _IS_REVERT_SQL); never join it to "the event behind the move" unchecked.
# The SQL below also relies on corrections never being voidable, so a revert's cause is never
# itself void.
STAGE_CHANGE_CAUSE_KEY = "event_activity_id"
# The causing activity id of a stage_change row aliased ``a``.
_CAUSE_SQL = f"json_extract(a.payload, '$.{STAGE_CHANGE_CAUSE_KEY}')"
# True when the stage_change row aliased ``a`` is a revert: its cause is a correction.
_IS_REVERT_SQL = (
    f"EXISTS (SELECT 1 FROM activities r WHERE r.type = 'correction' AND r.id = {_CAUSE_SQL})"
)


# R-17: the one definition of "void". An activity is void when a correction names it in
# voids_activity_id. Every void check (the counted-activity rule, the effective stage change,
# and the already-void refusals) is built from this predicate; change void semantics here only.
def _voiding_sql(target: str) -> str:
    """SQL true when the correction row aliased ``c`` voids the activity id ``target``."""
    return f"c.type = 'correction' AND c.voids_activity_id = {target}"


def _voided_sql(target: str) -> str:
    """SQL true when some correction voids the activity whose id is the SQL ``target``."""
    return f"EXISTS (SELECT 1 FROM activities c WHERE {_voiding_sql(target)})"


def _voided_by(conn: sqlite3.Connection, activity_id: int) -> int | None:
    """The id of the correction that voids ``activity_id``, or None when it is not void."""
    row = conn.execute(
        f"SELECT c.id FROM activities c WHERE {_voiding_sql('?')}", (activity_id,)
    ).fetchone()
    return None if row is None else int(row[0])


class EventError(ValueError):
    """An event field failed validation or a refusal rule; ``field`` names it."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


class LeadNotFoundError(EventError):
    """The lead id names no lead."""

    def __init__(self, lead_id: int) -> None:
        super().__init__("lead", f"no lead {lead_id}")
        self.lead_id = lead_id

    def __str__(self) -> str:
        return f"no lead {self.lead_id}"


@dataclass(frozen=True)
class RawEvent:
    """Operator input for one event, before validation."""

    lead_id: int
    type: str
    at: str
    note: str | None = None
    actor: str = DEFAULT_ACTOR
    stage: str | None = None
    need: str | None = None
    procurement_url: str | None = None


@dataclass(frozen=True)
class Event:
    """A validated event, ready to store."""

    lead_id: int
    type: str
    occurred_at: str
    note: str | None
    actor: str
    stage: str | None = None
    need: str | None = None
    procurement_url: str | None = None


class LoggedEvent(NamedTuple):
    """What log_event wrote: the event, and the stage change it caused (if any)."""

    event_id: int
    stage_change_id: int | None
    from_stage: str | None


def _clean(value: str | None) -> str | None:
    """Strip a text option; blank means not supplied."""
    if value is None:
        return None
    text = value.strip()
    return text or None


def validate_event(raw: RawEvent, now: str) -> Event:
    """Check an event against R-15; ``now`` is the current UTC time as stored."""
    if raw.type not in EVENT_TYPES:
        raise EventError("type", f"must be one of {', '.join(EVENT_TYPES)}")
    try:
        occurred_at = timeutil.parse_received(raw.at)
    except ValueError as exc:
        raise EventError("at", str(exc)) from None
    # Both are second-precision UTC strings ending in Z, so they compare as text.
    if occurred_at > now:
        raise EventError("at", f"is later than now ({timeutil.display_local(now)})")
    note = _clean(raw.note)
    if raw.type == "note" and note is None:
        raise EventError("note", "a note event needs --note text")
    actor = _clean(raw.actor)
    if actor is None:
        raise EventError("actor", "must not be empty")
    # The R-16 rule needs the lead's type (an out-of-list stage is refused first, with the
    # type's allowed stages), so it is checked in log_event; here blank text only stays blank.
    stage = _clean(raw.stage)
    need = None if raw.need is None else raw.need.strip()
    procurement_url = None if raw.procurement_url is None else raw.procurement_url.strip()
    return Event(
        lead_id=raw.lead_id,
        type=raw.type,
        occurred_at=occurred_at,
        note=note,
        actor=actor,
        stage=stage,
        need=need,
        procurement_url=procurement_url,
    )


def _is_http_url(value: str) -> bool:
    """True for an absolute http(s) URL with a host."""
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _rowid(cursor: sqlite3.Cursor) -> int:
    """Return the id of the row an INSERT just wrote."""
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return cursor.lastrowid


def _check_stage(lead_type: str, current: str, stage: str) -> None:
    """Refuse a stage outside the lead type's R-14 list, or the lead's current stage."""
    allowed = STAGES_BY_LEAD_TYPE.get(lead_type, ())
    listing = ", ".join(allowed)
    if stage not in allowed:
        raise EventError(
            "stage", f"{stage!r} is not a stage for {lead_type} leads; allowed: {listing}"
        )
    if stage == current:
        raise EventError("stage", f"lead is already at {stage}; allowed: {listing}")


def _check_qualification(event: Event) -> None:
    """R-16: buyer_need_confirmed needs a stated need or an http(s) procurement URL.

    --need and --procurement-url are refused with any other stage (or none). An empty value
    counts as given but blank.
    """
    if event.stage == QUALIFIED_STAGE:
        if not event.need and not event.procurement_url:
            raise EventError(
                "stage",
                f"{QUALIFIED_STAGE} needs --need (the confirmed need) or --procurement-url",
            )
        if event.procurement_url and not _is_http_url(event.procurement_url):
            raise EventError("procurement-url", "must be an absolute http or https URL")
    elif event.need is not None or event.procurement_url is not None:
        raise EventError(
            "need" if event.need is not None else "procurement-url",
            f"only allowed with --stage {QUALIFIED_STAGE}",
        )


def log_event(conn: sqlite3.Connection, event: Event) -> LoggedEvent:
    """Append the event and, with a stage, the move and its stage_change, in one transaction."""
    now = timeutil.utc_now()
    # Take the write lock before the first read, so the checks and the inserts see one state.
    conn.execute("BEGIN IMMEDIATE")
    try:
        lead = conn.execute(
            "SELECT id, type, stage FROM leads WHERE id = ?", (event.lead_id,)
        ).fetchone()
        if lead is None:
            raise LeadNotFoundError(event.lead_id)
        from_stage = str(lead[2])
        if event.stage is not None:
            _check_stage(str(lead[1]), from_stage, event.stage)
            _check_not_before_latest_stage_change(conn, event)
        _check_qualification(event)
        payload: dict[str, object] = {"event": event.type}
        if event.note is not None:
            payload["note"] = event.note
        if event.need:
            payload["need"] = event.need
        if event.procurement_url:
            payload["procurement_url"] = event.procurement_url
        event_id = _insert_activity(
            conn, event.lead_id, event.type, payload, event.actor, event.occurred_at, now
        )
        stage_change_id = None
        if event.stage is not None:
            conn.execute("UPDATE leads SET stage = ? WHERE id = ?", (event.stage, event.lead_id))
            # The cause of this move is the R-15 event just written (STAGE_CHANGE_CAUSE_KEY).
            stage_change_id = _insert_activity(
                conn,
                event.lead_id,
                "stage_change",
                {"from": from_stage, "to": event.stage, STAGE_CHANGE_CAUSE_KEY: event_id},
                event.actor,
                event.occurred_at,
                now,
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return LoggedEvent(event_id, stage_change_id, from_stage if stage_change_id else None)


def _check_not_before_latest_stage_change(conn: sqlite3.Connection, event: Event) -> None:
    """Refuse a stage change backdated before the lead's latest effective one (CCGE-060).

    leads.stage is the latest effective stage change by (occurred_at, id) (plan: "Effective
    stage change"). A move dated earlier than that one would set leads.stage while ranking
    below it, so a later correction would revert to the wrong stage; it is refused instead.
    A move at the same time ranks after it by id, so it is allowed.
    """
    latest = conn.execute(
        f"SELECT a.id, a.occurred_at FROM activities a WHERE {_EFFECTIVE_STAGE_CHANGE_SQL}"
        f" AND a.lead_id = ? AND NOT {_IS_REVERT_SQL}"
        " ORDER BY a.occurred_at DESC, a.id DESC LIMIT 1",
        (event.lead_id,),
    ).fetchone()
    if latest is not None and event.occurred_at < str(latest[1]):
        raise EventError(
            "at",
            f"is earlier than lead {event.lead_id}'s latest stage change (activity {latest[0]},"
            f" {timeutil.display_local(str(latest[1]))}); a stage change cannot be dated"
            " before it",
        )


def _insert_activity(
    conn: sqlite3.Connection,
    lead_id: int | None,
    activity_type: str,
    payload: dict[str, object],
    actor: str,
    occurred_at: str,
    recorded_at: str,
    voids_activity_id: int | None = None,
) -> int:
    """Insert one activity row (no contact) and return its id."""
    return _rowid(
        conn.execute(
            "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
            " recorded_at, voids_activity_id) VALUES (?, NULL, ?, ?, ?, ?, ?, ?)",
            (
                lead_id,
                activity_type,
                json.dumps(payload),
                actor,
                occurred_at,
                recorded_at,
                voids_activity_id,
            ),
        )
    )


# R-17: the one definition of a counted activity, over an activities row aliased ``a``. A
# correction never counts, nor does what a correction voids, nor a stage change whose causing
# event is void, nor a revert (a stage change caused by a correction), so history reads as if
# the voided move never happened; activities on test leads (R-3) do not count, entries with no
# lead do. "Void" itself is defined once, by _voiding_sql.
COUNTED_ACTIVITIES_SQL = (
    "a.type <> 'correction'"
    f" AND NOT {_voided_sql('a.id')}"
    f" AND NOT (a.type = 'stage_change' AND ({_voided_sql(_CAUSE_SQL)}"
    f" OR {_IS_REVERT_SQL}))"
    " AND (a.lead_id IS NULL OR EXISTS (SELECT 1 FROM leads l"
    " WHERE l.id = a.lead_id AND l.is_test = 0))"
)

# A stage change still in force: nothing voids it and nothing voids the activity that caused
# it (an event; a revert's cause is a correction, which is never voidable, so it stays).
_EFFECTIVE_STAGE_CHANGE_SQL = (
    f"a.type = 'stage_change' AND NOT {_voided_sql('a.id')} AND NOT {_voided_sql(_CAUSE_SQL)}"
)


def is_revert(conn: sqlite3.Connection, stage_change_id: int) -> bool:
    """True when the stage_change was written by a correction (its cause is a correction).

    False for a move caused by an R-15 event, and for an id that is not a stage_change.
    """
    row = conn.execute(
        f"SELECT {_IS_REVERT_SQL} FROM activities a WHERE a.id = ? AND a.type = 'stage_change'",
        (stage_change_id,),
    ).fetchone()
    return row is not None and bool(row[0])


def counted_activities(
    conn: sqlite3.Connection, activity_type: str | None = None
) -> list[sqlite3.Row]:
    """Counted activities (COUNTED_ACTIVITIES_SQL), oldest first, optionally of one type."""
    sql = f"SELECT a.* FROM activities a WHERE {COUNTED_ACTIVITIES_SQL}"
    params: tuple[object, ...] = ()
    if activity_type is not None:
        sql += " AND a.type = ?"
        params = (activity_type,)
    return list(conn.execute(sql + " ORDER BY a.occurred_at, a.id", params))


@dataclass(frozen=True)
class RawCorrection:
    """Operator input for a correction, before validation."""

    lead_id: int
    voids_id: int
    at: str
    note: str | None = None
    actor: str = DEFAULT_ACTOR


@dataclass(frozen=True)
class Correction:
    """A validated correction, ready to store."""

    lead_id: int
    voids_id: int
    occurred_at: str
    note: str | None
    actor: str


class LoggedCorrection(NamedTuple):
    """What log_correction wrote: the correction, and the stage revert it caused (if any)."""

    correction_id: int
    stage_change_id: int | None
    from_stage: str | None
    to_stage: str | None


def validate_correction(raw: RawCorrection, now: str) -> Correction:
    """Check a correction's time, note and actor; the target is checked in log_correction."""
    try:
        occurred_at = timeutil.parse_received(raw.at)
    except ValueError as exc:
        raise EventError("at", str(exc)) from None
    if occurred_at > now:
        raise EventError("at", f"is later than now ({timeutil.display_local(now)})")
    actor = _clean(raw.actor)
    if actor is None:
        raise EventError("actor", "must not be empty")
    return Correction(
        lead_id=raw.lead_id,
        voids_id=raw.voids_id,
        occurred_at=occurred_at,
        note=_clean(raw.note),
        actor=actor,
    )


def log_correction(conn: sqlite3.Connection, correction: Correction) -> LoggedCorrection:
    """Void one R-15 event of the lead; revert the stage it set if that is still the latest."""
    now = timeutil.utc_now()
    lead_id = correction.lead_id
    voids_id = correction.voids_id
    # The write lock comes before the already-void check, so two concurrent corrections
    # cannot both void the same activity (F-correctness-1).
    conn.execute("BEGIN IMMEDIATE")
    try:
        lead = conn.execute("SELECT stage FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            raise LeadNotFoundError(lead_id)
        target = conn.execute(
            "SELECT id, lead_id, type, occurred_at FROM activities WHERE id = ?", (voids_id,)
        ).fetchone()
        if target is None:
            raise EventError("voids", f"no activity {voids_id}")
        if target["lead_id"] != lead_id:
            raise EventError("voids", f"activity {voids_id} is not an activity of lead {lead_id}")
        if target["type"] not in EVENT_TYPES:
            raise EventError(
                "voids", f"activity {voids_id} is a {target['type']}, not an event (R-15)"
            )
        voided_by = _voided_by(conn, voids_id)
        if voided_by is not None:
            raise EventError(
                "voids", f"activity {voids_id} is already void (correction {voided_by})"
            )
        if correction.occurred_at < str(target["occurred_at"]):
            raise EventError(
                "at", f"is earlier than activity {voids_id}, which a correction must follow"
            )
        caused = conn.execute(
            f"SELECT a.id, a.payload FROM activities a WHERE {_EFFECTIVE_STAGE_CHANGE_SQL}"
            f" AND {_CAUSE_SQL} = ?",
            (voids_id,),
        ).fetchone()
        if caused is not None:
            # A revert (a stage change caused by a correction) only undoes a voided change, so
            # the latest change still in force is the newest effective one caused by an event.
            latest = conn.execute(
                f"SELECT a.id FROM activities a WHERE {_EFFECTIVE_STAGE_CHANGE_SQL}"
                f" AND a.lead_id = ? AND NOT {_IS_REVERT_SQL}"
                " ORDER BY a.occurred_at DESC, a.id DESC LIMIT 1",
                (lead_id,),
            ).fetchone()
            if latest is not None and latest["id"] != caused["id"]:
                raise EventError(
                    "voids",
                    f"lead {lead_id} has a later stage change (activity {latest['id']});"
                    " void the event behind it first",
                )
            # The revert is a stage change dated at the correction. Dated before the lead's
            # latest effective stage change (reverts included), it would set leads.stage while
            # ranking below that change by (occurred_at, id), so it is refused (F-correctness-4).
            newest = conn.execute(
                f"SELECT a.id, a.occurred_at FROM activities a WHERE {_EFFECTIVE_STAGE_CHANGE_SQL}"
                " AND a.lead_id = ? ORDER BY a.occurred_at DESC, a.id DESC LIMIT 1",
                (lead_id,),
            ).fetchone()
            if newest is not None and correction.occurred_at < str(newest["occurred_at"]):
                raise EventError(
                    "at",
                    f"is earlier than lead {lead_id}'s latest stage change (activity"
                    f" {newest['id']}, {timeutil.display_local(str(newest['occurred_at']))});"
                    " a correction that reverts a stage cannot be dated before it",
                )
        payload: dict[str, object] = {}
        if correction.note is not None:
            payload["note"] = correction.note
        correction_id = _insert_activity(
            conn,
            lead_id,
            "correction",
            payload,
            correction.actor,
            correction.occurred_at,
            now,
            voids_activity_id=voids_id,
        )
        stage_change_id = None
        from_stage = to_stage = None
        if caused is not None:
            from_stage = str(lead["stage"])
            to_stage = str(json.loads(caused["payload"])["from"])
            conn.execute("UPDATE leads SET stage = ? WHERE id = ?", (to_stage, lead_id))
            # A revert: its cause (STAGE_CHANGE_CAUSE_KEY) is this correction, not an event,
            # which is what makes is_revert / _IS_REVERT_SQL true for it.
            stage_change_id = _insert_activity(
                conn,
                lead_id,
                "stage_change",
                {"from": from_stage, "to": to_stage, STAGE_CHANGE_CAUSE_KEY: correction_id},
                correction.actor,
                correction.occurred_at,
                now,
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return LoggedCorrection(correction_id, stage_change_id, from_stage, to_stage)


# R-30: founder (or developer) hours and spend, entered per Denver calendar day.
PEOPLE = ("founder", "developer")
DEFAULT_PERSON = "founder"
TIME_KIND = "time_logged"
COST_KIND = "cost_logged"
MAX_HOURS = Decimal(24)
# The most one cost entry may be. An amount has at most 2 places, so an entry has at most
# 9 significant digits and sums of entries stay far inside Decimal's 28-digit default
# context: cost_totals are exact (F-correctness-6). Larger spend goes in several entries.
MAX_COST_USD = Decimal(1_000_000)
# ASCII digits only: \d also matches other scripts' digits (Arabic-Indic, fullwidth, ...),
# which Decimal() and date.fromisoformat() would then accept (F-correctness-5).
_PLAIN_DECIMAL = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


@dataclass(frozen=True)
class RawTime:
    """Operator input for one time entry, before validation."""

    hours: str
    date: str
    category: str
    person: str = DEFAULT_PERSON
    estimated: bool = False
    note: str | None = None
    actor: str = DEFAULT_ACTOR


@dataclass(frozen=True)
class TimeEntry:
    """A validated time entry, ready to store."""

    hours: Decimal
    date: date
    category: str
    person: str
    estimated: bool
    note: str | None
    actor: str


@dataclass(frozen=True)
class RawCost:
    """Operator input for one cost entry, before validation."""

    amount_usd: str
    date: str
    category: str
    estimated: bool = False
    note: str | None = None
    actor: str = DEFAULT_ACTOR


@dataclass(frozen=True)
class CostEntry:
    """A validated cost entry, ready to store."""

    amount_usd: Decimal
    date: date
    category: str
    estimated: bool
    note: str | None
    actor: str


def denver_today() -> date:
    """Today's calendar date in America/Denver."""
    return timeutil.local_date(timeutil.utc_now())


def _parse_amount(field: str, value: str) -> Decimal:
    """A plain positive decimal with at most 2 places (no sign, no exponent)."""
    text = value.strip()
    if not _PLAIN_DECIMAL.match(text):
        raise EventError(field, f"must be a plain decimal number like 1.5, got {value!r}")
    amount = Decimal(text)
    if amount <= 0:
        raise EventError(field, f"must be greater than 0, got {value!r}")
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise EventError(field, f"at most 2 decimal places, got {value!r}")
    return amount


def _parse_entry_date(value: str, today: date) -> date:
    """A YYYY-MM-DD date that is not after ``today`` (America/Denver)."""
    text = value.strip()
    if not _ISO_DATE.match(text):
        raise EventError("date", f"expected YYYY-MM-DD, got {value!r}")
    try:
        day = date.fromisoformat(text)
    except ValueError:
        raise EventError("date", f"not a valid date: {value!r}") from None
    if day > today:
        raise EventError("date", f"is after today in America/Denver ({today.isoformat()})")
    return day


def _entry_fields(category: str, note: str | None, actor: str) -> tuple[str, str | None, str]:
    """Shared checks: lowercase non-blank category, blank note dropped, non-blank actor."""
    cleaned = category.strip().lower()
    if not cleaned:
        raise EventError("category", "must not be empty")
    who = _clean(actor)
    if who is None:
        raise EventError("actor", "must not be empty")
    return cleaned, _clean(note), who


def validate_time(raw: RawTime, today: date) -> TimeEntry:
    """Check a time entry: hours in (0, 24], 2 places; date not after ``today``."""
    hours = _parse_amount("hours", raw.hours)
    if hours > MAX_HOURS:
        raise EventError("hours", f"at most {MAX_HOURS} in one day, got {raw.hours!r}")
    day = _parse_entry_date(raw.date, today)
    if raw.person not in PEOPLE:
        raise EventError("person", f"must be one of {', '.join(PEOPLE)}")
    category, note, actor = _entry_fields(raw.category, raw.note, raw.actor)
    return TimeEntry(hours, day, category, raw.person, raw.estimated, note, actor)


def validate_cost(raw: RawCost, today: date) -> CostEntry:
    """Check a cost entry: 0 < amount <= MAX_COST_USD, 2 places; date not after ``today``."""
    amount = _parse_amount("amount", raw.amount_usd)
    if amount > MAX_COST_USD:
        raise EventError(
            "amount", f"at most {MAX_COST_USD} US dollars in one entry, got {raw.amount_usd!r}"
        )
    day = _parse_entry_date(raw.date, today)
    category, note, actor = _entry_fields(raw.category, raw.note, raw.actor)
    return CostEntry(amount, day, category, raw.estimated, note, actor)


def _day_start(day: date) -> str:
    """The start of a Denver calendar day, as a stored UTC string."""
    return timeutil.to_utc_iso(datetime.combine(day, time(0), tzinfo=timeutil.DENVER))


def _insert_entry(
    conn: sqlite3.Connection, kind: str, payload: dict[str, object], day: date, actor: str
) -> int:
    """Append one time or cost entry (no lead) in its own transaction."""
    try:
        entry_id = _insert_activity(
            conn, None, kind, payload, actor, _day_start(day), timeutil.utc_now()
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return entry_id


def log_time(conn: sqlite3.Connection, entry: TimeEntry) -> int:
    """Append a time_logged activity and return its id."""
    payload: dict[str, object] = {
        "date": entry.date.isoformat(),
        "hours": str(entry.hours),
        "category": entry.category,
        "person": entry.person,
        "estimated": entry.estimated,
    }
    if entry.note is not None:
        payload["note"] = entry.note
    return _insert_entry(conn, TIME_KIND, payload, entry.date, entry.actor)


def log_cost(conn: sqlite3.Connection, entry: CostEntry) -> int:
    """Append a cost_logged activity and return its id."""
    payload: dict[str, object] = {
        "date": entry.date.isoformat(),
        "amount_usd": str(entry.amount_usd),
        "category": entry.category,
        "estimated": entry.estimated,
    }
    if entry.note is not None:
        payload["note"] = entry.note
    return _insert_entry(conn, COST_KIND, payload, entry.date, entry.actor)


def void_entry(
    conn: sqlite3.Connection,
    voids_id: int,
    kind: str,
    actor: str,
    now: str,
    note: str | None = None,
) -> int:
    """Void one time or cost entry with an appended correction (no lead); return its id."""
    if kind not in (TIME_KIND, COST_KIND):
        raise EventError("voids", f"kind must be {TIME_KIND} or {COST_KIND}")
    who = _clean(actor)
    if who is None:
        raise EventError("actor", "must not be empty")
    # The write lock comes before the already-void check (F-correctness-1).
    conn.execute("BEGIN IMMEDIATE")
    try:
        target = conn.execute(
            "SELECT id, type FROM activities WHERE id = ?", (voids_id,)
        ).fetchone()
        if target is None:
            raise EventError("voids", f"no activity {voids_id}")
        if target["type"] != kind:
            raise EventError("voids", f"activity {voids_id} is a {target['type']}, not {kind}")
        voided_by = _voided_by(conn, voids_id)
        if voided_by is not None:
            raise EventError(
                "voids", f"activity {voids_id} is already void (correction {voided_by})"
            )
        payload: dict[str, object] = {}
        cleaned = _clean(note)
        if cleaned is not None:
            payload["note"] = cleaned
        correction_id = _insert_activity(
            conn, None, "correction", payload, who, now, now, voids_activity_id=voids_id
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return correction_id


@dataclass(frozen=True)
class TimeTotals:
    """Counted hours over a date range: all, by person, and observed vs estimated."""

    total: Decimal
    by_person: dict[str, Decimal]
    observed: Decimal
    estimated: Decimal


@dataclass(frozen=True)
class CostTotals:
    """Counted spend over a date range: all, by category, and observed vs estimated."""

    total: Decimal
    by_category: dict[str, Decimal]
    observed: Decimal
    estimated: Decimal


def _entries_in_range(
    conn: sqlite3.Connection, kind: str, start: date, end: date
) -> list[dict[str, object]]:
    """Payloads of counted ``kind`` entries whose date is in [start, end] (inclusive)."""
    rows = conn.execute(
        f"SELECT a.payload FROM activities a WHERE {COUNTED_ACTIVITIES_SQL} AND a.type = ?"
        " AND json_extract(a.payload, '$.date') BETWEEN ? AND ? ORDER BY a.id",
        (kind, start.isoformat(), end.isoformat()),
    )
    return [json.loads(row[0]) for row in rows]


def time_totals(conn: sqlite3.Connection, start: date, end: date) -> TimeTotals:
    """Exact sums of counted hours dated in the inclusive Denver range [start, end]."""
    total = observed = estimated = Decimal(0)
    by_person: dict[str, Decimal] = {}
    for payload in _entries_in_range(conn, TIME_KIND, start, end):
        hours = Decimal(str(payload["hours"]))
        total += hours
        person = str(payload["person"])
        by_person[person] = by_person.get(person, Decimal(0)) + hours
        if payload["estimated"] is True:
            estimated += hours
        else:
            observed += hours
    return TimeTotals(total, by_person, observed, estimated)


def cost_totals(conn: sqlite3.Connection, start: date, end: date) -> CostTotals:
    """Exact sums of counted spend dated in the inclusive Denver range [start, end]."""
    total = observed = estimated = Decimal(0)
    by_category: dict[str, Decimal] = {}
    for payload in _entries_in_range(conn, COST_KIND, start, end):
        amount = Decimal(str(payload["amount_usd"]))
        total += amount
        category = str(payload["category"])
        by_category[category] = by_category.get(category, Decimal(0)) + amount
        if payload["estimated"] is True:
            estimated += amount
        else:
            observed += amount
    return CostTotals(total, by_category, observed, estimated)
