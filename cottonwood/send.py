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
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from cottonwood import claims, config, draft_claims, events

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


def sha256_file(path: Path) -> str:
    """The hex SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    """Write the sendable draft, or record the refusal and raise PrepareRefused."""
    lead = conn.execute("SELECT id, contact_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if lead is None:
        raise SendError("lead", f"no lead {lead_id}")
    try:
        data = draft.read_bytes()
    except FileNotFoundError:
        raise SendError("draft", f"no such file: {draft}") from None
    except OSError as exc:
        raise SendError("draft", f"cannot read {draft}: {exc.strerror or exc}") from None
    text = data.decode("utf-8", errors="replace")
    digest = hashlib.sha256(data).hexdigest()
    contact_id = lead["contact_id"]
    refusals: list[Refusal] = []
    lead_approval, draft_approval = _approvals(conn, lead_id, digest, refusals)
    _contact_checks(conn, contact_id, refusals)
    claim_ids = _claim_checks(conn, claims_path, claims_list, refusals)
    _evidence_check(conn, lead_id, settings.review.max_evidence_age_days, today, refusals)
    _content_checks(text, settings.sending, refusals)
    conn.execute("BEGIN IMMEDIATE")
    try:
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
        activity_id = _insert_prepared(
            conn,
            lead_id,
            contact_id,
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
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        sendable.write_bytes(data)
        try:
            conn.commit()
        except BaseException:
            sendable.unlink(missing_ok=True)
            raise
    except PrepareRefused:
        raise
    except BaseException:
        conn.rollback()
        raise
    return Prepared(activity_id, sendable)


def _insert_prepared(
    conn: sqlite3.Connection,
    lead_id: int,
    contact_id: int | None,
    payload: dict[str, object],
    actor: str,
    now: str,
) -> int:
    cursor = conn.execute(
        "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
        " recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (lead_id, contact_id, PREPARED_TYPE, json.dumps(payload), actor, now, now),
    )
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return cursor.lastrowid


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
    row = conn.execute(
        "SELECT MAX(substr(observed_at, 1, 10)) AS newest FROM evidence WHERE lead_id = ?",
        (lead_id,),
    ).fetchone()
    newest = row["newest"] if row is not None else None
    if newest is None:
        refusals.append(Refusal("evidence", f"lead {lead_id} has no evidence"))
        return
    try:
        observed = date.fromisoformat(str(newest))
    except ValueError:
        refusals.append(Refusal("evidence", f"newest evidence date {newest!r} is not a date"))
        return
    if observed < today - timedelta(days=max_age):
        refusals.append(
            Refusal(
                "evidence",
                f"newest evidence observed {observed.isoformat()} is older than {max_age} days",
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
