"""Contact eligibility changes with a recorded basis (R-8, R-24).

``eligible`` needs a public professional source URL and an unambiguous identity, and is refused
for a suppressed or deleted contact. Every change appends an ``eligibility_set`` activity whose
payload records only the old and new value and the kind of basis: no URL, name or address,
because activities are append-only and a deletion request must be able to clear contact data
(R-35). The source URL is stored on the contact row instead.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from cottonwood.validate import is_http_url

ELIGIBLE = "eligible"
INELIGIBLE = "ineligible"
UNKNOWN = "unknown"
VALUES = (ELIGIBLE, INELIGIBLE, UNKNOWN)
ACTIVITY_TYPE = "eligibility_set"
BASIS_SOURCE_URL = "public-source-url"
BASIS_MANUAL = "manual"

FIELD_SOURCE_URL = "source-url"
FIELD_CONTACT = "contact"
RULE_REQUIRED = "required"
RULE_URL = "url"
RULE_SUPPRESSED = "suppressed"
RULE_DELETED = "deleted"
RULE_IDENTITY = "identity"


class ContactNotFound(LookupError):
    """No contact has the given id."""

    def __init__(self, contact_id: int) -> None:
        super().__init__(f"no contact {contact_id}")
        self.contact_id = contact_id


class EligibilityError(ValueError):
    """The change is refused; ``failures`` names every failed check as (field, rule)."""

    def __init__(self, failures: list[tuple[str, str]]) -> None:
        super().__init__("; ".join(f"{field}: {rule}" for field, rule in failures))
        self.failures = failures


@dataclass(frozen=True)
class EligibilityChange:
    """The outcome: ``activity_id`` is None when the contact already had the value."""

    contact_id: int
    previous: str
    current: str
    activity_id: int | None

    def line(self) -> str:
        """What set-eligibility prints."""
        if self.activity_id is None:
            return f"contact {self.contact_id}: eligibility already {self.current}"
        return f"contact {self.contact_id}: eligibility {self.previous} -> {self.current}"


def set_eligibility(
    conn: sqlite3.Connection,
    contact_id: int,
    to: str,
    source_url: str | None,
    actor: str,
    now: str,
) -> EligibilityChange:
    """Change one contact's eligibility in its own transaction, or refuse with every reason."""
    if to not in VALUES:
        raise ValueError(f"eligibility must be one of {', '.join(VALUES)}, got {to!r}")
    conn.execute("BEGIN IMMEDIATE")
    try:
        change = _apply(conn, contact_id, to, source_url, actor, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return change


def _apply(
    conn: sqlite3.Connection,
    contact_id: int,
    to: str,
    source_url: str | None,
    actor: str,
    now: str,
) -> EligibilityChange:
    contact = conn.execute(
        "SELECT id, name, email, email_norm, eligibility, deleted_at FROM contacts WHERE id = ?",
        (contact_id,),
    ).fetchone()
    if contact is None:
        raise ContactNotFound(contact_id)
    previous = str(contact["eligibility"])
    # Checks run before the no-op test, so a suppressed address is always refused, even
    # when the contact already holds the requested value.
    failures = _failures(conn, contact, to, source_url)
    if failures:
        raise EligibilityError(failures)
    if previous == to:
        return EligibilityChange(contact_id, previous, to, None)
    if to == ELIGIBLE:
        conn.execute(
            "UPDATE contacts SET eligibility = ?, source_url = ? WHERE id = ?",
            (to, source_url, contact_id),
        )
    else:
        conn.execute("UPDATE contacts SET eligibility = ? WHERE id = ?", (to, contact_id))
    payload = {
        "from": previous,
        "to": to,
        "basis": BASIS_SOURCE_URL if to == ELIGIBLE else BASIS_MANUAL,
    }
    cursor = conn.execute(
        "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
        " recorded_at) VALUES (NULL, ?, ?, ?, ?, ?, ?)",
        (contact_id, ACTIVITY_TYPE, json.dumps(payload), actor, now, now),
    )
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return EligibilityChange(contact_id, previous, to, cursor.lastrowid)


def _failures(
    conn: sqlite3.Connection, contact: sqlite3.Row, to: str, source_url: str | None
) -> list[tuple[str, str]]:
    """Every check the change fails, in a stable order."""
    failures: list[tuple[str, str]] = []
    suppressed = _is_suppressed(conn, contact["email_norm"])
    if to == ELIGIBLE:
        if source_url is None or not source_url.strip():
            failures.append((FIELD_SOURCE_URL, RULE_REQUIRED))
        elif not is_http_url(source_url):
            failures.append((FIELD_SOURCE_URL, RULE_URL))
        if suppressed:
            failures.append((FIELD_CONTACT, RULE_SUPPRESSED))
        if contact["deleted_at"] is not None:
            failures.append((FIELD_CONTACT, RULE_DELETED))
        if not _identity_is_unambiguous(conn, contact):
            failures.append((FIELD_CONTACT, RULE_IDENTITY))
    elif to == UNKNOWN and suppressed:
        failures.append((FIELD_CONTACT, RULE_SUPPRESSED))
    return failures


def _is_suppressed(conn: sqlite3.Connection, email_norm: object) -> bool:
    if not isinstance(email_norm, str) or not email_norm:
        return False
    row = conn.execute("SELECT 1 FROM suppression WHERE email_norm = ?", (email_norm,)).fetchone()
    return row is not None


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _identity_is_unambiguous(conn: sqlite3.Connection, contact: sqlite3.Row) -> bool:
    """A name, an email, and no other not-deleted contact with the same normalized email."""
    email_norm = _text(contact["email_norm"])
    if _text(contact["name"]) is None or _text(contact["email"]) is None or email_norm is None:
        return False
    other = conn.execute(
        "SELECT 1 FROM contacts WHERE email_norm = ? AND id <> ? AND deleted_at IS NULL",
        (email_norm, contact["id"]),
    ).fetchone()
    return other is None
