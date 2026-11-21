"""Founder approvals for the outreach gate (R-18).

``approve`` records one founder approval as an append-only ``approval`` activity: who approved,
the day of the founder's written approval (America/Denver), the scope, the item approved and a
reference to that written approval (for example the email's date and subject). An approval
cannot be recorded without the reference. A ``draft`` approval names its lead and stores the
SHA-256 of the draft file's bytes, so the send gate can tell the approved draft from an edited
one. A ``claim`` approval also appends a ``claim_verified`` activity, which the claims file must
then agree with for the claim to count as verified (R-19, ``cottonwood.claims``).

``suppress`` adds an address to suppression without a lead (R-24). The address is normalized
exactly as every suppression check normalizes it; an existing entry is reported and left
exactly as it is, because suppression entries are never changed or deleted.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cottonwood import claims, events, normalize, timeutil

APPROVAL_TYPE = "approval"
SUPPRESS_SOURCE = "suppress"
SCOPES = ("lead", "draft", "claim", "audience", "offer")
TEXT_SCOPES = ("audience", "offer")


class GateError(ValueError):
    """A refused gate command, naming the field that failed."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


@dataclass(frozen=True)
class Approval:
    """One recorded approval."""

    activity_id: int
    scope: str
    item: str
    approver: str
    lead_id: int | None
    approved_on: date

    def line(self) -> str:
        """What approve prints."""
        if self.scope == "draft":
            return (
                f"approval {self.activity_id} recorded: draft {self.item}"
                f" for lead {self.lead_id} by {self.approver}"
            )
        line = f"approval {self.activity_id} recorded: {self.scope} {self.item} by {self.approver}"
        if self.scope == "claim":
            line += (
                f"; mark it verified in {claims.DEFAULT_CLAIMS_PATH.as_posix()} with"
                f" verified_by: {claims.yaml_value(self.approver)}"
                f" and verified_at: {self.approved_on.isoformat()}"
            )
        return line


@dataclass(frozen=True)
class SuppressResult:
    """The suppression entry for an address, and whether this call added it."""

    email_norm: str
    added: bool
    reason: str
    added_at: str

    def line(self) -> str:
        """What suppress prints."""
        if self.added:
            return f"suppressed {self.email_norm}"
        since = timeutil.local_date(self.added_at).isoformat()
        return f"{self.email_norm} already suppressed since {since} ({self.reason})"


def suppress(
    conn: sqlite3.Connection, email: str, reason: str, source: str | None, now: str
) -> SuppressResult:
    """Add a normalized address to suppression, or report the entry it already has."""
    try:
        email_norm = normalize.normalize_email(email)
    except ValueError as exc:
        raise GateError("email", str(exc).removeprefix("email ")) from None
    why = _required("reason", reason)
    origin = (source or "").strip() or SUPPRESS_SOURCE
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _insert_suppression(conn, email_norm, why, origin, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return result


def _insert_suppression(
    conn: sqlite3.Connection, email_norm: str, reason: str, source: str, now: str
) -> SuppressResult:
    """Inside the caller's transaction: add the entry, or report the one it already has."""
    row = conn.execute(
        "SELECT reason, added_at FROM suppression WHERE email_norm = ?", (email_norm,)
    ).fetchone()
    if row is not None:
        return SuppressResult(email_norm, False, str(row["reason"]), str(row["added_at"]))
    conn.execute(
        "INSERT INTO suppression (email_norm, reason, source, added_at) VALUES (?, ?, ?, ?)",
        (email_norm, reason, source, now),
    )
    return SuppressResult(email_norm, True, reason, now)


def approve(
    conn: sqlite3.Connection,
    scope: str,
    item: str,
    approver: str,
    reference: str,
    day: date,
    lead_id: int | None,
    actor: str,
    now: str,
    claims_path: Path = claims.DEFAULT_CLAIMS_PATH,
) -> Approval:
    """Record one founder approval in its own transaction, or raise GateError."""
    if scope not in SCOPES:
        raise GateError("scope", f"must be one of {', '.join(SCOPES)}, got {scope!r}")
    who = _required("approver", approver)
    ref = _required("reference", reference)
    by = _required("actor", actor)
    library: tuple[claims.Claim, ...] = ()
    if scope == "claim":
        try:
            library = claims.load_claims(claims_path)
        except claims.ClaimsError as exc:
            raise GateError("claims", str(exc)) from None
    conn.execute("BEGIN IMMEDIATE")
    try:
        if scope == "claim":
            approval = _apply_claim(conn, library, item, who, ref, day, lead_id, by, now)
        else:
            approval = _apply(conn, scope, item, who, ref, day, lead_id, by, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return approval


def _required(field: str, value: str) -> str:
    text = value.strip()
    if not text:
        raise GateError(field, "must not be empty")
    return text


def _apply(
    conn: sqlite3.Connection,
    scope: str,
    item: str,
    approver: str,
    reference: str,
    day: date,
    lead_id: int | None,
    actor: str,
    now: str,
) -> Approval:
    payload: dict[str, object] = {"scope": scope}
    if scope == "lead":
        approved_lead = _lead_item(conn, item)
        if lead_id is not None and lead_id != approved_lead:
            raise GateError("lead", f"--lead {lead_id} does not match the approved lead {item}")
        lead_id = approved_lead
        text = str(approved_lead)
    elif scope == "draft":
        if lead_id is None:
            raise GateError("lead", "a draft approval needs --lead, the lead the draft is for")
        _check_lead(conn, lead_id)
        text = item.strip()
        if not text:
            raise GateError("draft", "must name the draft file")
        payload["sha256"] = _draft_digest(Path(text))
    else:
        text = item.strip()
        if not text:
            raise GateError("item", f"the {scope} approved must not be empty")
        if lead_id is not None:
            _check_lead(conn, lead_id)
    payload.update(
        {
            "item": text,
            "approver": approver,
            "reference": reference,
            "approved_on": day.isoformat(),
        }
    )
    activity_id = events._insert_activity(
        conn,
        lead_id,
        APPROVAL_TYPE,
        payload,
        actor,
        events._day_start(day),
        now,
    )
    return Approval(activity_id, scope, text, approver, lead_id, day)


def _apply_claim(
    conn: sqlite3.Connection,
    library: tuple[claims.Claim, ...],
    item: str,
    approver: str,
    reference: str,
    day: date,
    lead_id: int | None,
    actor: str,
    now: str,
) -> Approval:
    claim_id = item.strip()
    claim = claims.find_claim(library, claim_id)
    if claim is None:
        raise GateError("claim", f"no claim {claim_id!r} in the claims file")
    if claim.status == "prohibited":
        raise GateError("claim", f"{claim_id} is prohibited and cannot be verified")
    standing = claims.standing_verification(conn, claim_id)
    if standing is not None:
        raise GateError(
            "claim",
            f"{claim_id} is already verified by {standing.verified_by} on"
            f" {standing.verified_at} (activity {standing.activity_id})",
        )
    if lead_id is not None:
        _check_lead(conn, lead_id)
    occurred_at = events._day_start(day)
    approval_id = events._insert_activity(
        conn,
        lead_id,
        APPROVAL_TYPE,
        {
            "scope": "claim",
            "item": claim_id,
            "approver": approver,
            "reference": reference,
            "approved_on": day.isoformat(),
        },
        actor,
        occurred_at,
        now,
    )
    events._insert_activity(
        conn,
        None,
        claims.CLAIM_VERIFIED_TYPE,
        {
            "claim_id": claim_id,
            "approval_activity_id": approval_id,
            "verified_by": approver,
            "verified_at": day.isoformat(),
        },
        actor,
        occurred_at,
        now,
    )
    return Approval(approval_id, "claim", claim_id, approver, lead_id, day)


def _lead_item(conn: sqlite3.Connection, item: str) -> int:
    text = item.strip()
    if not text.isascii() or not text.isdigit():
        raise GateError("lead", f"must be a lead id (a whole number), got {item!r}")
    lead_id = int(text)
    _check_lead(conn, lead_id)
    return lead_id


def _check_lead(conn: sqlite3.Connection, lead_id: int) -> None:
    if conn.execute("SELECT 1 FROM leads WHERE id = ?", (lead_id,)).fetchone() is None:
        raise GateError("lead", f"no lead {lead_id}")


def _draft_digest(path: Path) -> str:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise GateError("draft", f"no such file: {path}") from None
    except IsADirectoryError:
        raise GateError("draft", f"is a directory, not a draft file: {path}") from None
    except OSError as exc:
        raise GateError("draft", f"cannot read {path}: {exc.strerror or exc}") from None
    return hashlib.sha256(data).hexdigest()
