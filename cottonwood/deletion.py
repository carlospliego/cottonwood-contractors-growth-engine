"""Deletion requests (R-35): remove a person's details, including from activity records.

A deletion request is the one exception to append-only activities (R-17). In one
transaction the command makes sure the contact's address is suppressed (R-24: the entry is
kept, so the address is never imported or contacted again), clears the contact's personal
fields and its leads' free-text notes, removes the person's details from the payloads of the
contact's activities, and records the removal as a new activity with no personal data.

The activities_no_update trigger is dropped only inside that transaction and recreated from
its own stored definition before the commit, so any failure rolls both back together;
deleting or replacing activities stays refused throughout.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from cottonwood import gate
from cottonwood._shared import _rowid
from cottonwood.inbound import BUDGET_BASIS

DEFAULT_ACTOR = "founder"
ACTIVITY_TYPE = "deletion_request"
SUPPRESSION_REASON = "deletion_request"
SUPPRESSION_SOURCE = "deletion_request"
REMOVED = "[removed]"
# Payload keys that hold free text about the person; their values are cleared outright.
FREE_TEXT_KEYS = ("note", "need")
UPDATE_TRIGGER = "activities_no_update"

_CONTACT_FIELDS = ("name", "email", "email_norm", "phone_e164", "role", "source_url", "address")
_LEAD_FIELDS = ("hypothesis", "next_action", "property_location", "project_scope")


class DeletionError(ValueError):
    """A refused deletion request, naming the field that failed."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


@dataclass(frozen=True)
class DeletionResult:
    """What a deletion request changed."""

    contact_id: int
    activity_id: int
    activities_redacted: int
    suppressed: str | None
    suppression_added: bool

    def line(self) -> str:
        """What deletion-request prints."""
        if self.suppressed is None:
            kept = "no address to suppress"
        elif self.suppression_added:
            kept = f"suppressed {self.suppressed}"
        else:
            kept = f"kept the existing suppression of {self.suppressed}"
        return (
            f"contact {self.contact_id} deleted: personal fields cleared,"
            f" {self.activities_redacted} activity record(s) redacted, {kept};"
            f" recorded as activity {self.activity_id}"
        )


def _scrub(value: Any, secrets: tuple[str, ...]) -> Any:
    """Return value with every secret replaced inside strings, and free-text keys cleared."""
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, REMOVED)
        return value
    if isinstance(value, list):
        return [_scrub(item, secrets) for item in value]
    if isinstance(value, dict):
        return {
            key: None if key in FREE_TEXT_KEYS and item is not None else _scrub(item, secrets)
            for key, item in value.items()
        }
    return value


def _secrets(row: sqlite3.Row) -> tuple[str, ...]:
    """The contact's identifying values, longest first so a longer one is replaced whole."""
    values = {
        str(row[field]).strip()
        for field in ("name", "email", "email_norm", "phone_e164")
        if row[field] is not None and str(row[field]).strip()
    }
    return tuple(sorted(values, key=len, reverse=True))


def delete_contact(
    conn: sqlite3.Connection, contact_id: int, actor: str, now: str
) -> DeletionResult:
    """Carry out a deletion request for one contact, in one transaction."""
    who = actor.strip()
    if not who:
        raise DeletionError("actor", "must not be blank")
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _delete(conn, contact_id, who, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return result


def _delete(conn: sqlite3.Connection, contact_id: int, actor: str, now: str) -> DeletionResult:
    row = conn.execute(
        f"SELECT {', '.join(_CONTACT_FIELDS)}, deleted_at FROM contacts WHERE id = ?",
        (contact_id,),
    ).fetchone()
    if row is None:
        raise DeletionError("contact", f"no contact with id {contact_id}")

    suppressed: str | None = None
    added = False
    if row["email_norm"]:
        entry = gate._insert_suppression(
            conn, str(row["email_norm"]), SUPPRESSION_REASON, SUPPRESSION_SOURCE, now
        )
        suppressed, added = entry.email_norm, entry.added

    secrets = _secrets(row)
    redacted = _redact_activities(conn, contact_id, secrets)

    assignments = ", ".join(f"{field} = NULL" for field in _CONTACT_FIELDS)
    conn.execute(
        f"UPDATE contacts SET {assignments}, deleted_at = COALESCE(deleted_at, ?) WHERE id = ?",
        (now, contact_id),
    )
    lead_assignments = ", ".join(f"{field} = NULL" for field in _LEAD_FIELDS)
    conn.execute(f"UPDATE leads SET {lead_assignments} WHERE contact_id = ?", (contact_id,))
    # A budget the inquirer stated (log-inbound) is something they told us, so it goes; a
    # value we estimated ourselves (any other basis) stays (R-9, R-35).
    conn.execute(
        "UPDATE leads SET value_amount = NULL, value_basis = NULL"
        " WHERE contact_id = ? AND value_basis = ?",
        (contact_id, BUDGET_BASIS),
    )

    activity_id = _insert_removal(conn, contact_id, redacted, actor, now)
    return DeletionResult(contact_id, activity_id, redacted, suppressed, added)


def _insert_removal(
    conn: sqlite3.Connection, contact_id: int, redacted: int, actor: str, now: str
) -> int:
    """Record the removal itself, with no personal data in its payload."""
    payload = json.dumps({"reason": SUPPRESSION_REASON, "activities_redacted": redacted})
    cursor = conn.execute(
        "INSERT INTO activities (contact_id, type, payload, actor, occurred_at, recorded_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (contact_id, ACTIVITY_TYPE, payload, actor, now, now),
    )
    return _rowid(cursor)


def _redact_activities(conn: sqlite3.Connection, contact_id: int, secrets: tuple[str, ...]) -> int:
    """Rewrite the payloads of the contact's activities that hold personal details."""
    rows = conn.execute(
        "SELECT id, payload FROM activities"
        " WHERE contact_id = ? OR lead_id IN (SELECT id FROM leads WHERE contact_id = ?)"
        " ORDER BY id",
        (contact_id, contact_id),
    ).fetchall()
    changes: list[tuple[str, int]] = []
    for activity in rows:
        original = json.loads(activity["payload"])
        scrubbed = _scrub(original, secrets)
        if scrubbed != original:
            changes.append((json.dumps(scrubbed), int(activity["id"])))
    if not changes:
        return 0
    trigger = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?", (UPDATE_TRIGGER,)
    ).fetchone()
    if trigger is None:
        raise sqlite3.DatabaseError(f"trigger {UPDATE_TRIGGER} is missing")
    conn.execute(f"DROP TRIGGER {UPDATE_TRIGGER}")
    conn.executemany("UPDATE activities SET payload = ? WHERE id = ?", changes)
    conn.execute(str(trigger["sql"]))
    return len(changes)
