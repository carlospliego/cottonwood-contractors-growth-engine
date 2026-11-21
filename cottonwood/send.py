"""The send gate: prepare-send, the only producer of a sendable draft (R-21).

``prepare-send`` checks every R-21 condition and gathers every failure instead of stopping at
the first: a founder approval of the lead and of that exact draft (its SHA-256), an eligible and
unsuppressed contact, every claim the draft uses effectively verified, fresh evidence, and the
configured sender identity, postal address, opt-out line and ad identification in the draft.
When all pass it copies the draft's bytes to the output folder and appends a ``draft_prepared``
activity; otherwise it writes nothing and appends a ``prepare_refused`` activity naming the
failed checks. No email address is written to activities (contact data stays in ``contacts``).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from cottonwood import claims, config, draft_claims, eligibility, events, evidence, gate, normalize

PREPARED_TYPE = "draft_prepared"
REFUSED_TYPE = "prepare_refused"
DEFAULT_OUT_DIR = Path("out/send")
CHECKS = (
    "approval",
    "eligibility",
    "suppression",
    "claims",
    "evidence",
    "sender_identity",
    "postal_address",
    "opt_out",
    "ad_identification",
)


class SendError(ValueError):
    """A refused send-gate command input, naming the field."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


@dataclass(frozen=True)
class Refusal:
    """One failed R-21 check."""

    check: str
    detail: str

    def line(self) -> str:
        """What prepare-send prints on stderr for the failure."""
        return f"refused: {self.check}: {self.detail}"


class PrepareRefused(Exception):
    """prepare-send refused; every failed check, and the prepare_refused activity id."""

    def __init__(self, refusals: tuple[Refusal, ...], activity_id: int) -> None:
        super().__init__("; ".join(refusal.line() for refusal in refusals))
        self.refusals = refusals
        self.activity_id = activity_id


@dataclass(frozen=True)
class Prepared:
    """A sendable draft written by prepare-send."""

    activity_id: int
    sendable: Path

    def line(self) -> str:
        """What prepare-send prints."""
        return f"sendable draft written: {self.sendable.as_posix()} (prepared {self.activity_id})"


def sha256_bytes(data: bytes) -> str:
    """The hex SHA-256 of some bytes; every digest send records goes through here."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """The hex SHA-256 of a file's bytes."""
    return sha256_bytes(path.read_bytes())


def prepare_send(
    conn: sqlite3.Connection,
    lead_id: int,
    draft: Path,
    out_dir: Path,
    claims_path: Path,
    claims_list: Path,
    settings: config.Config,
    today: date,
    actor: str,
    now: str,
) -> Prepared:
    """Write the sendable draft, or record the refusal and raise PrepareRefused.

    Every R-21 check reads the database inside the BEGIN IMMEDIATE transaction that records
    the outcome, so an opt-out, approval void or claim change committed by another writer
    before the lock is taken is seen, and none can land between the checks and the write.
    """
    try:
        data = draft.read_bytes()
    except FileNotFoundError:
        raise SendError("draft", f"no such file: {draft}") from None
    except OSError as exc:
        raise SendError("draft", f"cannot read {draft}: {exc.strerror or exc}") from None
    text = data.decode("utf-8", errors="replace")
    digest = sha256_bytes(data)
    conn.execute("BEGIN IMMEDIATE")
    try:
        lead = conn.execute("SELECT id, contact_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            raise SendError("lead", f"no lead {lead_id}")
        contact_id = lead["contact_id"]
        refusals: list[Refusal] = []
        lead_approval, draft_approval = _approvals(conn, lead_id, digest, refusals)
        _contact_checks(conn, contact_id, refusals)
        claim_ids = _claim_checks(conn, claims_path, claims_list, refusals)
        _evidence_check(conn, lead_id, settings.review.max_evidence_age_days, today, refusals)
        _content_checks(text, settings.sending, refusals)
        if refusals:
            refused_id = events._insert_activity(
                conn,
                lead_id,
                REFUSED_TYPE,
                {"draft": draft.as_posix(), "checks": _check_names(refusals)},
                actor,
                now,
                now,
            )
            conn.commit()
            raise PrepareRefused(tuple(refusals), refused_id)
        sendable = out_dir / draft.name
        if sendable.exists() and sendable.read_bytes() != data:
            raise SendError(
                "out", f"{sendable.as_posix()} already holds a different sendable draft"
            )
        activity_id = _insert(
            conn,
            lead_id,
            contact_id,
            PREPARED_TYPE,
            {
                "draft": draft.as_posix(),
                "sha256": digest,
                "sendable": sendable.as_posix(),
                "claim_ids": list(claim_ids),
                "lead_approval_id": lead_approval,
                "draft_approval_id": draft_approval,
            },
            actor,
            now,
            now,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        existed = sendable.exists()
        _write_atomically(sendable, data)
        try:
            conn.commit()
        except BaseException:
            if not existed:
                sendable.unlink(missing_ok=True)
            raise
    except PrepareRefused:
        raise
    except BaseException:
        conn.rollback()
        raise
    return Prepared(activity_id, sendable)


def _write_atomically(target: Path, data: bytes) -> None:
    """Write data to target so a failure never leaves a partial file under target's name.

    The bytes go to a temporary file in the same folder, which is renamed over target only
    once it is complete; on any failure the temporary file is removed.
    """
    temporary = target.with_name(f".{target.name}.{os.getpid()}.partial")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _standing_approvals(conn: sqlite3.Connection, lead_id: int, scope: str) -> list[sqlite3.Row]:
    """The lead's unvoided approvals of a scope, newest first."""
    rows = conn.execute(
        "SELECT a.id, a.payload FROM activities AS a"
        f" WHERE a.lead_id = ? AND a.type = 'approval' AND NOT {events._voided_sql('a.id')}"
        " ORDER BY a.id DESC",
        (lead_id,),
    )
    return [row for row in rows if _payload(row["payload"]).get("scope") == scope]


def _approvals(
    conn: sqlite3.Connection, lead_id: int, digest: str, refusals: list[Refusal]
) -> tuple[int | None, int | None]:
    """The lead approval and the approval of this exact draft, recording what is missing."""
    leads = _standing_approvals(conn, lead_id, "lead")
    lead_approval = int(leads[0]["id"]) if leads else None
    if lead_approval is None:
        refusals.append(Refusal("approval", f"no founder approval of lead {lead_id}"))
    drafts = _standing_approvals(conn, lead_id, "draft")
    matching = [row for row in drafts if _payload(row["payload"]).get("sha256") == digest]
    draft_approval = int(matching[0]["id"]) if matching else None
    if draft_approval is None:
        if drafts:
            detail = "the draft differs from the approved draft (sha256 does not match)"
        else:
            detail = f"no founder approval of a draft for lead {lead_id}"
        refusals.append(Refusal("approval", detail))
    return lead_approval, draft_approval


def _contact_checks(
    conn: sqlite3.Connection, contact_id: int | None, refusals: list[Refusal]
) -> None:
    contact = None
    if contact_id is not None:
        contact = conn.execute(
            "SELECT id, email_norm, eligibility, deleted_at FROM contacts WHERE id = ?",
            (contact_id,),
        ).fetchone()
    if contact is None or not contact["email_norm"] or contact["deleted_at"] is not None:
        refusals.append(Refusal("eligibility", "the lead has no contact with an email address"))
        return
    if contact["eligibility"] != "eligible":
        refusals.append(
            Refusal("eligibility", f"contact {contact['id']} is {contact['eligibility']}")
        )
    suppressed = conn.execute(
        "SELECT 1 FROM suppression WHERE email_norm = ?", (contact["email_norm"],)
    ).fetchone()
    if suppressed is not None:
        refusals.append(Refusal("suppression", f"contact {contact['id']}'s address is suppressed"))


def _claim_checks(
    conn: sqlite3.Connection, claims_path: Path, claims_list: Path, refusals: list[Refusal]
) -> tuple[str, ...]:
    try:
        claim_ids = draft_claims.load_draft_claims(claims_list)
    except draft_claims.DraftClaimsError as exc:
        refusals.append(Refusal("claims", str(exc)))
        return ()
    if not claim_ids:
        return ()
    try:
        library = claims.load_claims(claims_path)
    except claims.ClaimsError as exc:
        refusals.append(Refusal("claims", str(exc)))
        return claim_ids
    statuses = {status.id: status for status in claims.effective_statuses(conn, library)}
    for claim_id in claim_ids:
        status = statuses.get(claim_id)
        if status is None:
            refusals.append(Refusal("claims", f"{claim_id} is not in the claims file"))
        elif status.status != "verified":
            refusals.append(Refusal("claims", f"{claim_id} is {status.status}"))
    return claim_ids


def _evidence_check(
    conn: sqlite3.Connection,
    lead_id: int,
    max_age: int | None,
    today: date,
    refusals: list[Refusal],
) -> None:
    if max_age is None:
        refusals.append(
            Refusal("evidence", "no maximum evidence age configured (review.max_evidence_age_days)")
        )
        return
    found = evidence.newest(conn, lead_id)
    if found is None:
        refusals.append(Refusal("evidence", f"lead {lead_id} has no evidence"))
        return
    try:
        effective = date.fromisoformat(found.date)
    except ValueError:
        refusals.append(Refusal("evidence", f"newest evidence date {found.date!r} is not a date"))
        return
    if effective < today - timedelta(days=max_age):
        refusals.append(
            Refusal(
                "evidence",
                f"newest evidence {found.basis} {effective.isoformat()}"
                f" is older than {max_age} days",
            )
        )


def _content_checks(text: str, sending: config.SendingConfig, refusals: list[Refusal]) -> None:
    required = (
        ("sender_identity", sending.sender_identity, "sending.sender_identity", True),
        ("postal_address", sending.postal_address, "sending.postal_address", True),
        ("opt_out", sending.opt_out_line, "sending.opt_out_line", True),
        ("ad_identification", sending.ad_identification, "sending.ad_identification", False),
    )
    for check, value, key, mandatory in required:
        if not value:
            if mandatory:
                refusals.append(Refusal(check, f"not configured ({key} is empty)"))
            continue
        if value not in text:
            refusals.append(Refusal(check, f"the draft does not contain the configured {key}"))


def _check_names(refusals: list[Refusal]) -> list[str]:
    """The failed check names, each once, in CHECKS order."""
    failed = {refusal.check for refusal in refusals}
    return [check for check in CHECKS if check in failed]


def _payload(text: object) -> dict[str, object]:
    try:
        value = json.loads(str(text))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


SENT_TYPE = "sent"
VIOLATION_TYPE = "gate_violation"
NO_PREPARED = "no prepared draft"
MESSAGE_DIFFERS = "message differs from the prepared draft"
RECIPIENT_DIFFERS = "recipient differs from the prepared contact"
RECIPIENT_SUPPRESSED = "recipient suppressed since preparation"


@dataclass(frozen=True)
class Outreach:
    """A recorded send and, when it bypassed the gate, the violation."""

    lead_id: int
    sent_id: int
    violation_id: int | None
    reasons: tuple[str, ...]

    def line(self) -> str:
        """What log-outreach prints on stdout."""
        return f"send recorded: lead {self.lead_id} (activity {self.sent_id})"

    def violation_lines(self) -> list[str]:
        """What log-outreach prints on stderr, one line per reason."""
        return [f"gate violation: {reason}" for reason in self.reasons]


def log_outreach(
    conn: sqlite3.Connection,
    lead_id: int,
    prepared_id: int | None,
    recipient: str,
    source_url: str,
    message: Path,
    sender: str,
    sent_on: str,
    today: date,
    provider_message_id: str | None,
    actor: str,
    now: str,
) -> Outreach:
    """Record a send the founder performed, and a gate violation when it bypassed the gate."""
    who = sender.strip()
    if not who:
        raise SendError("sender", "must not be empty")
    try:
        day = events._parse_entry_date(sent_on, today)
    except events.EventError as exc:
        raise SendError("date", str(exc).removeprefix("date: ")) from None
    url = source_url.strip()
    if not events._is_http_url(url):
        raise SendError("source_url", f"must be an http(s) URL, got {source_url!r}")
    try:
        recipient_norm = normalize.normalize_email(recipient)
    except ValueError as exc:
        raise SendError("recipient", str(exc).removeprefix("email ")) from None
    try:
        message_digest = sha256_file(message)
    except FileNotFoundError:
        raise SendError("message", f"no such file: {message}") from None
    except OSError as exc:
        raise SendError("message", f"cannot read {message}: {exc.strerror or exc}") from None
    lead = conn.execute("SELECT id, contact_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if lead is None:
        raise SendError("lead", f"no lead {lead_id}")
    conn.execute("BEGIN IMMEDIATE")
    try:
        prepared = _prepared(conn, lead_id, prepared_id)
        reasons: list[str] = []
        contact_id = lead["contact_id"]
        if prepared is None:
            reasons.append(NO_PREPARED)
        else:
            contact_id = prepared["contact_id"]
            payload = _payload(prepared["payload"])
            if payload.get("sha256") != message_digest:
                reasons.append(MESSAGE_DIFFERS)
        contact_norm = _contact_email_norm(conn, contact_id)
        matches = contact_norm is not None and contact_norm == recipient_norm
        if prepared is not None:
            if not matches:
                reasons.append(RECIPIENT_DIFFERS)
            if _suppressed_since(conn, recipient_norm, prepared["recorded_at"]):
                reasons.append(RECIPIENT_SUPPRESSED)
        sent_id = _insert(
            conn,
            lead_id,
            contact_id,
            SENT_TYPE,
            {
                "prepared": prepared_id,
                "source_url": url,
                "message": message.as_posix(),
                "message_sha256": message_digest,
                "sender": who,
                "sent_on": day.isoformat(),
                "provider_message_id": (provider_message_id or "").strip() or None,
                "recipient_matches": matches,
            },
            actor,
            events._day_start(day),
            now,
        )
        violation_id = None
        if reasons:
            violation_id = _insert(
                conn,
                lead_id,
                contact_id,
                VIOLATION_TYPE,
                {"sent_activity_id": sent_id, "reasons": reasons},
                actor,
                now,
                now,
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return Outreach(lead_id, sent_id, violation_id, tuple(reasons))


def _prepared(
    conn: sqlite3.Connection, lead_id: int, prepared_id: int | None
) -> sqlite3.Row | None:
    """The draft_prepared activity named by --prepared when it belongs to this lead."""
    if prepared_id is None:
        return None
    row: sqlite3.Row | None = conn.execute(
        "SELECT id, contact_id, payload, recorded_at FROM activities"
        " WHERE id = ? AND lead_id = ? AND type = ?",
        (prepared_id, lead_id, PREPARED_TYPE),
    ).fetchone()
    return row


def _contact_email_norm(conn: sqlite3.Connection, contact_id: int | None) -> str | None:
    if contact_id is None:
        return None
    row = conn.execute("SELECT email_norm FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    return str(row["email_norm"]) if row is not None and row["email_norm"] else None


def _suppressed_since(conn: sqlite3.Connection, email_norm: str, since: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM suppression WHERE email_norm = ? AND added_at >= ?", (email_norm, since)
    ).fetchone()
    return row is not None


def _insert(
    conn: sqlite3.Connection,
    lead_id: int | None,
    contact_id: int | None,
    activity_type: str,
    payload: dict[str, object],
    actor: str,
    occurred_at: str,
    recorded_at: str,
) -> int:
    cursor = conn.execute(
        "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
        " recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (lead_id, contact_id, activity_type, json.dumps(payload), actor, occurred_at, recorded_at),
    )
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return cursor.lastrowid


REPLY_TYPE = "reply"
SUPPRESSED_TYPE = "suppressed"
REPLY_SOURCE = "log-reply"
REPLY_TYPES = (
    "interested",
    "not_now",
    "not_relevant",
    "referral",
    "opt_out",
    "bounce",
    "other",
)


@dataclass(frozen=True)
class Reply:
    """A recorded reply and what it changed on the lead's contact."""

    lead_id: int
    reply_type: str
    activity_id: int
    suppressed_contact: int | None = None
    eligibility: eligibility.EligibilityChange | None = None

    def lines(self) -> list[str]:
        """What log-reply prints on stdout."""
        lines = [
            f"reply recorded: lead {self.lead_id} {self.reply_type} (activity {self.activity_id})"
        ]
        if self.suppressed_contact is not None:
            lines.append(f"suppressed: contact {self.suppressed_contact}")
        if self.eligibility is not None:
            lines.append(self.eligibility.line())
        return lines


def log_reply(
    conn: sqlite3.Connection,
    lead_id: int,
    reply_type: str,
    received_on: str | None,
    note: str | None,
    today: date,
    actor: str,
    now: str,
) -> Reply:
    """Record a reply; opt_out suppresses the contact's address and bounce makes it ineligible."""
    if reply_type not in REPLY_TYPES:
        raise SendError("type", f"must be one of {', '.join(REPLY_TYPES)}, got {reply_type!r}")
    if received_on is None:
        day = today
    else:
        try:
            day = events._parse_entry_date(received_on, today)
        except events.EventError as exc:
            raise SendError("date", str(exc).removeprefix("date: ")) from None
    lead = conn.execute("SELECT id, contact_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if lead is None:
        raise SendError("lead", f"no lead {lead_id}")
    contact_id = lead["contact_id"]
    email_norm = _contact_email_norm(conn, contact_id)
    if reply_type in ("opt_out", "bounce") and (contact_id is None or email_norm is None):
        raise SendError("contact", f"lead {lead_id} has no contact with an email address")
    text = (note or "").strip() or None
    conn.execute("BEGIN IMMEDIATE")
    try:
        reply_id = _insert(
            conn,
            lead_id,
            contact_id,
            REPLY_TYPE,
            {"type": reply_type, "received_on": day.isoformat(), "note": text},
            actor,
            events._day_start(day),
            now,
        )
        suppressed_contact = None
        change = None
        if reply_type == "opt_out" and email_norm is not None:
            result = gate._insert_suppression(
                conn, email_norm, f"opt-out reply to lead {lead_id}", REPLY_SOURCE, now
            )
            _insert(
                conn,
                lead_id,
                contact_id,
                SUPPRESSED_TYPE,
                {"reply_activity_id": reply_id, "source": REPLY_SOURCE, "added": result.added},
                actor,
                now,
                now,
            )
            suppressed_contact = contact_id
        elif reply_type == "bounce" and contact_id is not None:
            change = eligibility._apply(conn, contact_id, eligibility.INELIGIBLE, None, actor, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return Reply(lead_id, reply_type, reply_id, suppressed_contact, change)
