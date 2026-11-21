"""Inbound inquiries: validate what the inquirer supplied and record it as a lead (R-1 to R-3)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from cottonwood import normalize, timeutil

CHANNELS = ("form", "phone")
SEGMENTS = ("commercial", "residential", "unknown")
BUDGET_BASIS = "buyer-stated"
DEFAULT_ACTOR = "developer"


class InquiryError(ValueError):
    """An inquiry field failed validation; ``field`` names it."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


@dataclass(frozen=True)
class RawInquiry:
    """Operator input, before validation. Text fields are None when not supplied."""

    channel: str
    received: str
    segment: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    location: str | None = None
    scope: str | None = None
    budget: str | None = None
    is_test: bool = False
    actor: str = DEFAULT_ACTOR


@dataclass(frozen=True)
class Inquiry:
    """A validated inquiry, ready to store. Every optional field is None unless supplied."""

    channel: str
    received_at: str
    segment: str
    name: str | None
    email: str | None
    email_norm: str | None
    phone_e164: str | None
    company: str | None
    location: str | None
    scope: str | None
    budget: str | None
    is_test: bool
    actor: str


def _clean(value: str | None) -> str | None:
    """Strip a text option; blank means the inquirer did not supply it."""
    if value is None:
        return None
    text = value.strip()
    return text or None


def _parse_budget(value: str) -> str:
    """Return a stated budget as exact decimal text; reject non-numbers and negatives.

    Exponent form (1e5) is refused: Decimal would keep it as '1E+5' and show it that way.
    """
    if "e" in value.lower():
        raise InquiryError("budget", f"write the amount in plain digits, not 1e5 form: {value!r}")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise InquiryError("budget", f"not a decimal number: {value!r}") from None
    if not amount.is_finite():
        raise InquiryError("budget", f"not a finite number: {value!r}")
    if amount < 0:
        raise InquiryError("budget", f"must not be negative: {value!r}")
    if amount == 0:
        return "0"
    return str(amount)


def validate(raw: RawInquiry) -> Inquiry:
    """Check and normalize operator input; raise InquiryError naming the first bad field."""
    if raw.channel not in CHANNELS:
        raise InquiryError("channel", f"must be one of {', '.join(CHANNELS)}: {raw.channel!r}")
    if raw.segment not in SEGMENTS:
        raise InquiryError("segment", f"must be one of {', '.join(SEGMENTS)}: {raw.segment!r}")
    try:
        received_at = timeutil.parse_received(raw.received)
    except ValueError as exc:
        raise InquiryError("received", str(exc)) from None

    name = _clean(raw.name)
    email = _clean(raw.email)
    phone = _clean(raw.phone)
    if name is None and email is None and phone is None:
        raise InquiryError("name/email/phone", "supply at least one of --name, --email, --phone")

    email_norm = None
    if email is not None:
        try:
            email_norm = normalize.normalize_email(email)
        except ValueError as exc:
            raise InquiryError("email", str(exc)) from None
    phone_e164 = None
    if phone is not None:
        try:
            phone_e164 = normalize.normalize_phone(phone)
        except ValueError as exc:
            raise InquiryError("phone", str(exc)) from None

    budget_text = _clean(raw.budget)
    budget = None if budget_text is None else _parse_budget(budget_text)
    actor = _clean(raw.actor)
    if actor is None:
        raise InquiryError("actor", "must not be empty")

    return Inquiry(
        channel=raw.channel,
        received_at=received_at,
        segment=raw.segment,
        name=name,
        email=email,
        email_norm=email_norm,
        phone_e164=phone_e164,
        company=_clean(raw.company),
        location=_clean(raw.location),
        scope=_clean(raw.scope),
        budget=budget,
        is_test=raw.is_test,
        actor=actor,
    )


def _organization_id(conn: sqlite3.Connection, company: str, now: str) -> int:
    """Reuse the organization with the same normalized name, else create it."""
    name_norm = normalize.normalize_name(company)
    row = conn.execute(
        "SELECT id FROM organizations WHERE name_norm = ? ORDER BY id LIMIT 1", (name_norm,)
    ).fetchone()
    if row is not None:
        return int(row[0])
    cursor = conn.execute(
        "INSERT INTO organizations (name, name_norm, created_at) VALUES (?, ?, ?)",
        (company, name_norm, now),
    )
    return _rowid(cursor)


def _rowid(cursor: sqlite3.Cursor) -> int:
    """Return the id of the row an INSERT just wrote."""
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return cursor.lastrowid


def find_same_day_duplicates(
    conn: sqlite3.Connection, email_norm: str | None, phone_e164: str | None, received_at: str
) -> list[int]:
    """Ids of inbound inquiries sharing the email or phone on the same Denver date (R-2).

    Test inquiries count too, so the labeled test submissions exercise the check.
    """
    if email_norm is None and phone_e164 is None:
        return []
    rows = conn.execute(
        "SELECT leads.id, leads.received_at FROM leads"
        " JOIN contacts ON contacts.id = leads.contact_id"
        " WHERE leads.type = 'inbound_inquiry'"
        " AND (contacts.email_norm = ? OR contacts.phone_e164 = ?)"
        " ORDER BY leads.id",
        (email_norm, phone_e164),
    ).fetchall()
    day = timeutil.local_date(received_at)
    return [
        int(row[0])
        for row in rows
        if row[1] is not None and timeutil.local_date(str(row[1])) == day
    ]


def log_inquiry(
    conn: sqlite3.Connection, inquiry: Inquiry, duplicate_of: Sequence[int] = ()
) -> int:
    """Store one inquiry (organization, contact, lead, activity) atomically; return the lead id.

    ``duplicate_of`` lists the lead ids the operator confirmed this inquiry duplicates.
    """
    now = timeutil.utc_now()
    try:
        org_id = None
        if inquiry.company is not None:
            org_id = _organization_id(conn, inquiry.company, now)
        contact_id = _rowid(
            conn.execute(
                "INSERT INTO contacts (organization_id, name, email, email_norm, phone_e164)"
                " VALUES (?, ?, ?, ?, ?)",
                (org_id, inquiry.name, inquiry.email, inquiry.email_norm, inquiry.phone_e164),
            )
        )
        lead_id = _rowid(
            conn.execute(
                "INSERT INTO leads (type, organization_id, contact_id, stage, segment, channel,"
                " property_location, project_scope, value_amount, value_basis, is_test,"
                " received_at)"
                " VALUES ('inbound_inquiry', ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    org_id,
                    contact_id,
                    inquiry.segment,
                    inquiry.channel,
                    inquiry.location,
                    inquiry.scope,
                    inquiry.budget,
                    None if inquiry.budget is None else BUDGET_BASIS,
                    1 if inquiry.is_test else 0,
                    inquiry.received_at,
                ),
            )
        )
        # The payload stays free of personal data: activities are append-only, so anything
        # written here could never be removed on a deletion request (R-35).
        payload = {
            "channel": inquiry.channel,
            "segment": inquiry.segment,
            "is_test": inquiry.is_test,
            "duplicate_of": list(duplicate_of),
        }
        conn.execute(
            "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
            " recorded_at) VALUES (?, ?, 'inquiry_logged', ?, ?, ?, ?)",
            (lead_id, contact_id, json.dumps(payload), inquiry.actor, inquiry.received_at, now),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return lead_id
