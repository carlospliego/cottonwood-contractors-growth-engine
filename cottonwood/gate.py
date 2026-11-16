"""Founder approvals for the outreach gate (R-18).

``approve`` records one founder approval as an append-only ``approval`` activity: who approved,
the day of the founder's written approval (America/Denver), the scope, the item approved and a
reference to that written approval (for example the email's date and subject). An approval
cannot be recorded without the reference. A ``draft`` approval names its lead and stores the
SHA-256 of the draft file's bytes, so the send gate can tell the approved draft from an edited
one.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cottonwood import events

APPROVAL_TYPE = "approval"
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
        return f"approval {self.activity_id} recorded: {self.scope} {self.item} by {self.approver}"


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
) -> Approval:
    """Record one founder approval in its own transaction, or raise GateError."""
    if scope not in SCOPES:
        raise GateError("scope", f"must be one of {', '.join(SCOPES)}, got {scope!r}")
    who = _required("approver", approver)
    ref = _required("reference", reference)
    by = _required("actor", actor)
    if scope == "claim":
        raise GateError("scope", "claim approvals are not available yet")
    conn.execute("BEGIN IMMEDIATE")
    try:
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
