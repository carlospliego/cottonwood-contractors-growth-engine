"""Hand-review results for researched prospects (R-11).

``mark-reviewed`` records one result per lead: ``relevant``, ``irrelevant`` or ``fabricated``
(unsupported by its evidence), with the reviewer and the review date. The weekly report counts
``hand_review`` activities per motion and counts ``fabricated`` as a data-quality failure, so a
lead keeps at most one standing result: a second review needs ``--replace``, which appends a
``correction`` voiding the earlier result (activities are append-only, R-17).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date

from cottonwood import events

ACTIVITY_TYPE = "hand_review"
RESULTS = ("relevant", "irrelevant", "fabricated")
REVIEWABLE_TYPES = (events.DIRECT_CANDIDATE, events.RELATIONSHIP_PROSPECT)
REPLACE_NOTE = "replaced by mark-reviewed --replace"
CORRECTION_TYPE = "correction"  # the activity type events' void predicate recognizes


@dataclass(frozen=True)
class HandReviewResult:
    """The recorded review and, with --replace, the correction that voided the earlier one."""

    lead_id: int
    result: str
    activity_id: int
    replaced_activity_id: int | None

    def line(self) -> str:
        """What mark-reviewed prints."""
        return f"lead {self.lead_id}: hand review {self.result}"


def parse_review_date(value: str | None, today: date) -> date:
    """The --date value (default today in America/Denver); not after today."""
    if value is None:
        return today
    return events._parse_entry_date(value, today)


def mark_reviewed(
    conn: sqlite3.Connection,
    lead_id: int,
    result: str,
    reviewer: str,
    day: date,
    replace: bool,
    actor: str,
    now: str,
) -> HandReviewResult:
    """Record one hand-review result in its own transaction, or raise events.EventError."""
    if result not in RESULTS:
        raise events.EventError("result", f"must be one of {', '.join(RESULTS)}, got {result!r}")
    who = reviewer.strip()
    if not who:
        raise events.EventError("reviewer", "must not be empty")
    by = actor.strip()
    if not by:
        raise events.EventError("actor", "must not be empty")
    conn.execute("BEGIN IMMEDIATE")
    try:
        recorded = _apply(conn, lead_id, result, who, day, replace, by, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return recorded


def standing_review(conn: sqlite3.Connection, lead_id: int) -> sqlite3.Row | None:
    """The lead's latest hand_review that no correction voids, or None."""
    row: sqlite3.Row | None = conn.execute(
        "SELECT a.id, a.payload FROM activities AS a"
        f" WHERE a.lead_id = ? AND a.type = ? AND NOT {events._voided_sql('a.id')}"
        " ORDER BY a.id DESC LIMIT 1",
        (lead_id, ACTIVITY_TYPE),
    ).fetchone()
    return row


def review_result(row: sqlite3.Row) -> str:
    """The result stored in a hand_review row's payload ('' when unreadable)."""
    try:
        payload = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError):
        return ""
    value = payload.get("result") if isinstance(payload, dict) else None
    return value if isinstance(value, str) else ""


def _apply(
    conn: sqlite3.Connection,
    lead_id: int,
    result: str,
    reviewer: str,
    day: date,
    replace: bool,
    actor: str,
    now: str,
) -> HandReviewResult:
    lead = conn.execute("SELECT id, type FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if lead is None:
        raise events.LeadNotFoundError(lead_id)
    if lead["type"] not in REVIEWABLE_TYPES:
        raise events.EventError(
            "lead",
            f"type must be {' or '.join(REVIEWABLE_TYPES)} for a hand review, got {lead['type']}",
        )
    standing = standing_review(conn, lead_id)
    replaced: int | None = None
    if standing is not None:
        if not replace:
            raise events.EventError(
                "lead",
                f"already has hand review {review_result(standing)} (activity {standing['id']});"
                " use --replace to record a new result",
            )
        replaced = int(standing["id"])
        events._insert_activity(
            conn,
            lead_id,
            CORRECTION_TYPE,
            {"note": REPLACE_NOTE},
            actor,
            now,
            now,
            voids_activity_id=replaced,
        )
    activity_id = events._insert_activity(
        conn,
        lead_id,
        ACTIVITY_TYPE,
        {"result": result, "reviewer": reviewer},
        actor,
        events._day_start(day),
        now,
    )
    return HandReviewResult(lead_id, result, activity_id, replaced)
