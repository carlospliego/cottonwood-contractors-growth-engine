"""prospects-import: researched records into organizations, contacts, leads and evidence (R-5–R-7).

Each record is written all-or-nothing inside its own savepoint; a rejected record writes only
an ``import_rejected`` activity. Activity payloads carry no personal data, because activities
are append-only and a deletion request must be able to remove contact data (R-35).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from cottonwood import timeutil
from cottonwood.validate import RELATIONSHIP, ProspectRecord, Rejection, record_label

IMPORTED = "imported"
IMPORT_REJECTED = "import_rejected"
IMPORTED_STAGE = "researched"
RULE_REFERRER = "referrer"
ELIGIBILITY_UNKNOWN = "unknown"
ELIGIBILITY_INELIGIBLE = "ineligible"
_SAVEPOINT = "prospect_record"


@dataclass(frozen=True)
class RecordOutcome:
    """What happened to one record of the file."""

    number: int
    record_id: str | None
    lead_id: int | None = None
    lead_type: str | None = None
    created: bool = False
    new_evidence: int = 0
    rejection: Rejection | None = None

    def line(self) -> str:
        """The line the CLI prints for this record (stderr for a rejection)."""
        if self.rejection is not None:
            return self.rejection.line()
        label = record_label(self.number, self.record_id)
        if self.created:
            return f"{label}: created lead {self.lead_id} ({self.lead_type})"
        return f"{label}: matched lead {self.lead_id} (+{self.new_evidence} evidence)"


@dataclass(frozen=True)
class ImportResult:
    """Every record's outcome, in file order."""

    outcomes: tuple[RecordOutcome, ...]

    @property
    def imported(self) -> int:
        """Records that created a lead."""
        return sum(1 for o in self.outcomes if o.rejection is None and o.created)

    @property
    def matched(self) -> int:
        """Records that matched a stored lead."""
        return sum(1 for o in self.outcomes if o.rejection is None and not o.created)

    @property
    def rejected(self) -> int:
        """Records that were refused."""
        return sum(1 for o in self.outcomes if o.rejection is not None)

    def summary(self) -> str:
        """The last line the CLI prints."""
        return f"imported {self.imported}, matched {self.matched}, rejected {self.rejected}"


def import_records(
    conn: sqlite3.Connection,
    file_name: str,
    records: Sequence[ProspectRecord | Rejection],
    actor: str,
) -> ImportResult:
    """Import validated records and record rejections, committing once at the end.

    ``records`` are in file order: a ProspectRecord is written inside its own savepoint, so a
    failure leaves nothing of it; a Rejection (from validation, or a referrer that is not a
    stored relationship prospect) writes one ``import_rejected`` activity with no lead.
    """
    now = timeutil.utc_now()
    outcomes: list[RecordOutcome] = []
    conn.execute("BEGIN")
    try:
        for record in records:
            if isinstance(record, Rejection):
                outcomes.append(_reject(conn, file_name, record, actor, now))
                continue
            rejection = _referrer_rejection(conn, record)
            if rejection is not None:
                outcomes.append(_reject(conn, file_name, rejection, actor, now))
                continue
            conn.execute(f"SAVEPOINT {_SAVEPOINT}")
            try:
                outcome = _write(conn, file_name, record, actor, now)
            except BaseException:
                conn.execute(f"ROLLBACK TO {_SAVEPOINT}")
                conn.execute(f"RELEASE {_SAVEPOINT}")
                raise
            conn.execute(f"RELEASE {_SAVEPOINT}")
            outcomes.append(outcome)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return ImportResult(tuple(outcomes))


def _referrer_rejection(conn: sqlite3.Connection, record: ProspectRecord) -> Rejection | None:
    """A Rejection when referred_by names no stored relationship-prospect lead (R-12)."""
    if record.referred_by is None:
        return None
    row = conn.execute("SELECT type FROM leads WHERE id = ?", (record.referred_by,)).fetchone()
    if row is not None and row[0] == RELATIONSHIP:
        return None
    return Rejection(record.number, record.record_id, "referred_by", RULE_REFERRER)


def _reject(
    conn: sqlite3.Connection, file_name: str, rejection: Rejection, actor: str, now: str
) -> RecordOutcome:
    """Write the import_rejected activity of one refused record (a data-quality failure)."""
    payload = {
        "file": file_name,
        "record": rejection.number,
        "record_id": rejection.record_id,
        "field": rejection.field,
        "rule": rejection.rule,
    }
    _activity(conn, None, None, IMPORT_REJECTED, payload, actor, now)
    return RecordOutcome(rejection.number, rejection.record_id, rejection=rejection)


def _write(
    conn: sqlite3.Connection, file_name: str, record: ProspectRecord, actor: str, now: str
) -> RecordOutcome:
    """Create the record's organization, contact, lead and evidence; return its outcome."""
    org_id = _insert_organization(conn, record, now)
    contact_id = None if record.contact is None else _insert_contact(conn, record, org_id)
    lead_id = _insert_lead(conn, record, org_id, contact_id)
    added = _insert_evidence(conn, record, lead_id)
    payload = {
        "file": file_name,
        "record": record.number,
        "record_id": record.record_id,
        "created": True,
        "new_evidence": added,
    }
    _activity(conn, lead_id, contact_id, IMPORTED, payload, actor, now)
    return RecordOutcome(
        record.number,
        record.record_id,
        lead_id=lead_id,
        lead_type=record.type,
        created=True,
        new_evidence=added,
    )


def _insert_organization(conn: sqlite3.Connection, record: ProspectRecord, now: str) -> int:
    return _rowid(
        conn.execute(
            "INSERT INTO organizations (name, name_norm, domain_norm, type, category, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                record.organization_name,
                record.organization_name_norm,
                record.organization_domain_norm,
                record.organization_type,
                record.organization_category,
                now,
            ),
        )
    )


def _is_suppressed(conn: sqlite3.Connection, email_norm: str | None) -> bool:
    if email_norm is None:
        return False
    row = conn.execute("SELECT 1 FROM suppression WHERE email_norm = ?", (email_norm,)).fetchone()
    return row is not None


def _insert_contact(conn: sqlite3.Connection, record: ProspectRecord, org_id: int) -> int:
    """A new contact: ineligible when its address is suppressed, else unknown (R-8, R-24)."""
    contact = record.contact
    assert contact is not None
    eligibility = (
        ELIGIBILITY_INELIGIBLE if _is_suppressed(conn, contact.email_norm) else ELIGIBILITY_UNKNOWN
    )
    return _rowid(
        conn.execute(
            "INSERT INTO contacts (organization_id, name, email, email_norm, phone_e164, role,"
            " source_url, eligibility) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                org_id,
                contact.name,
                contact.email,
                contact.email_norm,
                contact.phone_e164,
                contact.role,
                contact.source_url,
                eligibility,
            ),
        )
    )


def _insert_lead(
    conn: sqlite3.Connection, record: ProspectRecord, org_id: int, contact_id: int | None
) -> int:
    return _rowid(
        conn.execute(
            "INSERT INTO leads (type, organization_id, contact_id, stage, property_location,"
            " hypothesis, verified_facts, next_action, founder_time_h, value_amount, value_basis,"
            " referred_by, is_test) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.type,
                org_id,
                contact_id,
                IMPORTED_STAGE,
                record.property_location,
                record.hypothesis,
                json.dumps(list(record.verified_facts)),
                record.next_action,
                record.founder_time_h,
                record.value_amount,
                record.value_basis,
                record.referred_by,
                1 if record.is_test else 0,
            ),
        )
    )


def _insert_evidence(conn: sqlite3.Connection, record: ProspectRecord, lead_id: int) -> int:
    """Insert the record's evidence items for the lead; return how many were added."""
    for item in record.evidence:
        conn.execute(
            "INSERT INTO evidence (lead_id, url, observed_at, published_at, excerpt, observation,"
            " kind) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                lead_id,
                item.url,
                item.observed_at,
                item.published_at,
                item.excerpt,
                item.observation,
                item.kind,
            ),
        )
    return len(record.evidence)


def _activity(
    conn: sqlite3.Connection,
    lead_id: int | None,
    contact_id: int | None,
    activity_type: str,
    payload: dict[str, object],
    actor: str,
    now: str,
) -> int:
    return _rowid(
        conn.execute(
            "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
            " recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (lead_id, contact_id, activity_type, json.dumps(payload), actor, now, now),
        )
    )


def _rowid(cursor: sqlite3.Cursor) -> int:
    """Return the id of the row an INSERT just wrote."""
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return cursor.lastrowid
