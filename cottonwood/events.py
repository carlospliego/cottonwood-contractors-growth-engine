"""Lead events: validate and record what happened on a lead (R-15)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

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


@dataclass(frozen=True)
class Event:
    """A validated event, ready to store."""

    lead_id: int
    type: str
    occurred_at: str
    note: str | None
    actor: str


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
    return Event(
        lead_id=raw.lead_id, type=raw.type, occurred_at=occurred_at, note=note, actor=actor
    )


def _rowid(cursor: sqlite3.Cursor) -> int:
    """Return the id of the row an INSERT just wrote."""
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return cursor.lastrowid


def log_event(conn: sqlite3.Connection, event: Event) -> int:
    """Append one event activity for the lead in one transaction; return its id."""
    now = timeutil.utc_now()
    try:
        lead = conn.execute("SELECT id FROM leads WHERE id = ?", (event.lead_id,)).fetchone()
        if lead is None:
            raise LeadNotFoundError(event.lead_id)
        payload: dict[str, object] = {"event": event.type}
        if event.note is not None:
            payload["note"] = event.note
        activity_id = _rowid(
            conn.execute(
                "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
                " recorded_at) VALUES (?, NULL, ?, ?, ?, ?, ?)",
                (
                    event.lead_id,
                    event.type,
                    json.dumps(payload),
                    event.actor,
                    event.occurred_at,
                    now,
                ),
            )
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return activity_id
