"""prospects-import: researched records into organizations, contacts, leads and evidence (R-5–R-7).

Each record is written all-or-nothing inside its own savepoint; a rejected record writes only
an ``import_rejected`` activity. Re-importing creates no duplicates (R-7): a record whose lead is
already stored only gains the evidence not yet stored, never changes a stored value, and reports
each field whose incoming value differs. Activity payloads carry no personal data, because
activities are append-only and a deletion request must be able to remove contact data (R-35).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from cottonwood import normalize, terminal, timeutil
from cottonwood.validate import (
    RELATIONSHIP,
    ProspectEvidence,
    ProspectRecord,
    Rejection,
    record_label,
)

IMPORTED = "imported"
IMPORT_REJECTED = "import_rejected"
IMPORTED_STAGE = "researched"
RULE_REFERRER = "referrer"
_SQLITE_MAX_INT = 2**63 - 1
ELIGIBILITY_UNKNOWN = "unknown"
ELIGIBILITY_INELIGIBLE = "ineligible"
_SAVEPOINT = "prospect_record"


@dataclass(frozen=True)
class Difference:
    """A field of a matched record whose incoming value differs from the stored one."""

    field: str
    stored: str
    incoming: str


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
    differences: tuple[Difference, ...] = ()

    def label(self) -> str:
        """``record N`` with the record_id in parentheses when the record has one."""
        return record_label(self.number, self.record_id)

    def line(self) -> str:
        """The line the CLI prints for this record (stderr for a rejection)."""
        if self.rejection is not None:
            return self.rejection.line()
        if self.created:
            return f"{self.label()}: created lead {self.lead_id} ({self.lead_type})"
        if self.new_evidence:
            return f"{self.label()}: matched lead {self.lead_id} (+{self.new_evidence} evidence)"
        return f"{self.label()}: matched lead {self.lead_id}"

    def difference_lines(self) -> list[str]:
        """One line per differing field of a matched record (stored values are kept)."""
        return [
            f"{self.label()}: {d.field} differs: stored '{d.stored}', incoming '{d.incoming}'"
            " (kept stored)"
            for d in self.differences
        ]


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

    ``records`` are in file order: a ProspectRecord is matched or written inside its own
    savepoint, so a failure leaves nothing of it, and later records see earlier ones as stored;
    a Rejection (from validation, or a referrer that is not a stored relationship prospect)
    writes one ``import_rejected`` activity with no lead.
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
                outcome = _import_one(conn, file_name, record, actor, now)
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


def check_records(
    conn: sqlite3.Connection, records: Sequence[ProspectRecord | Rejection]
) -> list[Rejection]:
    """The rejections import_records would report for ``records``, writing nothing (R-25).

    Validation rejections are returned as they are; a valid record is also checked for a
    referrer that is not a stored relationship prospect, with a read-only query.
    """
    rejections: list[Rejection] = []
    for record in records:
        if isinstance(record, Rejection):
            rejections.append(record)
            continue
        rejection = _referrer_rejection(conn, record)
        if rejection is not None:
            rejections.append(rejection)
    return rejections


def _referrer_rejection(conn: sqlite3.Connection, record: ProspectRecord) -> Rejection | None:
    """A Rejection when referred_by names no stored relationship-prospect lead (R-12)."""
    if record.referred_by is None:
        return None
    if record.referred_by > _SQLITE_MAX_INT:  # cannot name a stored lead; SQLite cannot bind it
        return Rejection(record.number, record.record_id, "referred_by", RULE_REFERRER)
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


def _import_one(
    conn: sqlite3.Connection, file_name: str, record: ProspectRecord, actor: str, now: str
) -> RecordOutcome:
    """Match the record's lead or create it, add new evidence, and log one imported activity.

    A matched lead with no new evidence writes nothing, so an identical re-import leaves every
    table as it was.
    """
    org_id = _find_organization(conn, record)
    lead = None if org_id is None else _find_lead(conn, record, org_id)
    if lead is not None:
        lead_id = int(lead["id"])
        contact_id = None if lead["contact_id"] is None else int(lead["contact_id"])
        differences = _differences(conn, record, lead)
        created = False
    else:
        if org_id is None:
            org_id = _insert_organization(conn, record, now)
        contact_id = None
        if record.contact is not None:
            contact_id = _find_contact(conn, record, org_id)
            if contact_id is None:
                contact_id = _insert_contact(conn, record, org_id)
        lead_id = _insert_lead(conn, record, org_id, contact_id)
        differences = ()
        created = True
    added = _insert_new_evidence(conn, record, lead_id)
    if created or added:
        payload = {
            "file": file_name,
            "record": record.number,
            "record_id": record.record_id,
            "created": created,
            "new_evidence": added,
        }
        _activity(conn, lead_id, contact_id, IMPORTED, payload, actor, now)
    return RecordOutcome(
        record.number,
        record.record_id,
        lead_id=lead_id,
        lead_type=record.type,
        created=created,
        new_evidence=added,
        differences=differences,
    )


# --- Matching (R-7) -----------------------------------------------------------------------


def _find_organization(conn: sqlite3.Connection, record: ProspectRecord) -> int | None:
    """The stored organization with the record's normalized domain, else (only when the record
    has no domain) the one with its normalized name."""
    if record.organization_domain_norm is not None:
        row = conn.execute(
            "SELECT id FROM organizations WHERE domain_norm = ?",
            (record.organization_domain_norm,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM organizations WHERE name_norm = ? ORDER BY id LIMIT 1",
            (record.organization_name_norm,),
        ).fetchone()
    return None if row is None else int(row[0])


def _location_key(value: object) -> str:
    """Property locations compare trimmed and case-insensitively; empty equals absent."""
    return value.strip().casefold() if isinstance(value, str) else ""


def _find_lead(conn: sqlite3.Connection, record: ProspectRecord, org_id: int) -> sqlite3.Row | None:
    """The stored lead with the same organization, type and property location."""
    key = _location_key(record.property_location)
    rows = conn.execute(
        "SELECT * FROM leads WHERE organization_id = ? AND type = ? ORDER BY id",
        (org_id, record.type),
    ).fetchall()
    return next((row for row in rows if _location_key(row["property_location"]) == key), None)


def _find_contact(conn: sqlite3.Connection, record: ProspectRecord, org_id: int) -> int | None:
    """A not-deleted contact with the record's normalized email, else (only without an email)
    one in the same organization with the same normalized name."""
    contact = record.contact
    if contact is None:
        return None
    if contact.email_norm is not None:
        row = conn.execute(
            "SELECT id FROM contacts WHERE email_norm = ? AND deleted_at IS NULL"
            " ORDER BY id LIMIT 1",
            (contact.email_norm,),
        ).fetchone()
        return None if row is None else int(row[0])
    name_norm = normalize.normalize_name(contact.name or "")
    if not name_norm:
        return None
    rows = conn.execute(
        "SELECT id, name FROM contacts WHERE organization_id = ? AND deleted_at IS NULL"
        " ORDER BY id",
        (org_id,),
    ).fetchall()
    return next(
        (
            int(row["id"])
            for row in rows
            if normalize.normalize_name(row["name"] or "") == name_norm
        ),
        None,
    )


def _evidence_key(
    url: object, observed_at: object, excerpt: object, observation: object
) -> tuple[object, ...]:
    return (url, observed_at, excerpt, observation)


def _insert_new_evidence(conn: sqlite3.Connection, record: ProspectRecord, lead_id: int) -> int:
    """Insert the record's evidence items the lead does not already have; return how many."""
    stored = {
        _evidence_key(row["url"], row["observed_at"], row["excerpt"], row["observation"])
        for row in conn.execute(
            "SELECT url, observed_at, excerpt, observation FROM evidence WHERE lead_id = ?",
            (lead_id,),
        )
    }
    added = 0
    for item in record.evidence:
        key = _evidence_key(item.url, item.observed_at, item.excerpt, item.observation)
        if key in stored:
            continue
        _insert_evidence(conn, lead_id, item)
        stored.add(key)
        added += 1
    return added


# --- Differences --------------------------------------------------------------------------


def _shown(value: object) -> str:
    """How a value appears in a difference line."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list | tuple):
        return "; ".join(str(item) for item in value)
    return str(value)


def _stored_facts(value: object) -> list[str] | None:
    if not isinstance(value, str):
        return None
    try:
        facts = json.loads(value)
    except json.JSONDecodeError:
        return None
    return [str(fact) for fact in facts] if isinstance(facts, list) else None


def _stored_checklist(value: object) -> dict[str, str]:
    """A lead's stored checklist answers by item key ({} when none or unreadable)."""
    if not isinstance(value, str):
        return {}
    try:
        answers = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(answers, dict):
        return {}
    return {str(key): str(answer) for key, answer in answers.items()}


def checklist_json(checklist: tuple[tuple[str, str], ...]) -> str | None:
    """The leads.checklist text for a record's answers: a key-sorted JSON object, or NULL."""
    return json.dumps(dict(checklist), sort_keys=True) if checklist else None


def _column(row: sqlite3.Row | None, key: str) -> object:
    """A column of an optional row (None when there is no row)."""
    return None if row is None else row[key]


def _differences(
    conn: sqlite3.Connection, record: ProspectRecord, lead: sqlite3.Row
) -> tuple[Difference, ...]:
    """Fields whose incoming non-empty value differs from the matched lead's stored value."""
    org = conn.execute(
        "SELECT name, domain_norm, type, category FROM organizations WHERE id = ?",
        (lead["organization_id"],),
    ).fetchone()
    contact_row = None
    if lead["contact_id"] is not None:
        contact_row = conn.execute(
            "SELECT name, phone_e164, address, role, source_url FROM contacts WHERE id = ?",
            (lead["contact_id"],),
        ).fetchone()
    contact = record.contact
    pairs: list[tuple[str, object, object]] = [
        ("organization.name", org["name"], record.organization_name),
        ("organization.domain", org["domain_norm"], record.organization_domain_norm),
        ("organization.type", org["type"], record.organization_type),
        ("organization.category", org["category"], record.organization_category),
    ]
    if contact is not None:
        pairs += [
            ("contact.name", _column(contact_row, "name"), contact.name),
            ("contact.phone", _column(contact_row, "phone_e164"), contact.phone_e164),
            ("contact.address", _column(contact_row, "address"), contact.address),
            ("contact.role", _column(contact_row, "role"), contact.role),
            ("contact.source_url", _column(contact_row, "source_url"), contact.source_url),
        ]
    pairs += [
        ("hypothesis", lead["hypothesis"], record.hypothesis or None),
        (
            "verified_facts",
            _stored_facts(lead["verified_facts"]),
            list(record.verified_facts) or None,
        ),
        ("next_action", lead["next_action"], record.next_action),
        ("founder_time_h", lead["founder_time_h"], record.founder_time_h),
        ("value.amount", lead["value_amount"], record.value_amount),
        ("value.basis", lead["value_basis"], record.value_basis),
        ("referred_by", lead["referred_by"], record.referred_by),
        ("is_test", bool(lead["is_test"]), record.is_test),
    ]
    if not record.is_test_given:
        pairs = [pair for pair in pairs if pair[0] != "is_test"]
    stored_checklist = _stored_checklist(lead["checklist"])
    pairs += [
        (f"checklist.{key}", stored_checklist.get(key), answer) for key, answer in record.checklist
    ]
    return tuple(
        Difference(field, terminal.printable(_shown(stored)), terminal.printable(_shown(incoming)))
        for field, stored, incoming in pairs
        if incoming is not None and incoming != "" and incoming != stored
    )


# --- Inserts ------------------------------------------------------------------------------


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
            "INSERT INTO contacts (organization_id, name, email, email_norm, phone_e164, address,"
            " role, source_url, eligibility) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                org_id,
                contact.name,
                contact.email,
                contact.email_norm,
                contact.phone_e164,
                contact.address,
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
            " referred_by, is_test, checklist) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                checklist_json(record.checklist),
            ),
        )
    )


def _insert_evidence(conn: sqlite3.Connection, lead_id: int, item: ProspectEvidence) -> None:
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
