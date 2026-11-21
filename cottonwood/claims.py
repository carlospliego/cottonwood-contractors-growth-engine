"""The outreach claims library (R-19).

``config/claims.yaml`` lists each claim a draft may make, with its status (``verified``,
``unverified`` or ``prohibited``), its evidence or source, ``verified_by`` and ``verified_at``.
The file is edited by hand and never rewritten by the CLI. A claim counts as ``verified`` only
when the file says so *and* a recorded founder claim approval agrees: ``approve claim ID`` writes
a ``claim_verified`` activity, and its verifier and date must match the file. Neither a hand edit
nor an approval alone verifies a claim.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from cottonwood import events

STATUSES = ("verified", "unverified", "prohibited")
DEFAULT_CLAIMS_PATH = Path("config/claims.yaml")
CLAIM_VERIFIED_TYPE = "claim_verified"
NOT_APPROVED_NOTE = "marked verified but no matching claim approval"

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ClaimsError(ValueError):
    """A claims file that cannot be used, naming the file, the claim and the field."""

    def __init__(self, path: Path, location: str, message: str) -> None:
        super().__init__(f"{path}: {location}: {message}")
        self.path = path
        self.location = location
        self.message = message


@dataclass(frozen=True)
class Claim:
    """One claim as the file states it."""

    id: str
    text: str
    status: str
    evidence: str
    verified_by: str | None
    verified_at: str | None


@dataclass(frozen=True)
class Verification:
    """A standing claim_verified activity."""

    activity_id: int
    verified_by: str
    verified_at: str


@dataclass(frozen=True)
class ClaimStatus:
    """A claim's effective status and, when the file and the approvals disagree, why."""

    id: str
    status: str
    note: str | None

    def line(self) -> str:
        """What ``cottonwood claims`` prints for the claim."""
        if self.note is None:
            return f"{self.id}: {self.status}"
        return f"{self.id}: {self.status} ({self.note})"


def load_claims(path: Path) -> tuple[Claim, ...]:
    """Read and check the claims file, or raise ClaimsError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ClaimsError(path, "file", "not found") from None
    except UnicodeDecodeError as exc:
        raise ClaimsError(path, "file", f"is not UTF-8 text (byte {exc.start})") from None
    except OSError as exc:
        raise ClaimsError(path, "file", f"cannot be read: {exc.strerror or exc}") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ClaimsError(path, "file", f"is not valid YAML: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        raise ClaimsError(path, "claims", "the file must have a top-level 'claims' list")
    claims: list[Claim] = []
    seen: set[str] = set()
    for index, entry in enumerate(data["claims"], start=1):
        claim = _claim(path, index, entry)
        if claim.id in seen:
            raise ClaimsError(path, f"claims[{index}] ({claim.id})", "id: is a duplicate")
        seen.add(claim.id)
        claims.append(claim)
    return tuple(claims)


def find_claim(claims: tuple[Claim, ...], claim_id: str) -> Claim | None:
    """The claim with this id, or None."""
    return next((claim for claim in claims if claim.id == claim_id), None)


def standing_verification(conn: sqlite3.Connection, claim_id: str) -> Verification | None:
    """The latest claim_verified activity for the claim that no correction voids, or None."""
    rows = conn.execute(
        "SELECT a.id, a.payload FROM activities AS a"
        f" WHERE a.type = ? AND NOT {events._voided_sql('a.id')}"
        " ORDER BY a.id DESC",
        (CLAIM_VERIFIED_TYPE,),
    )
    for row in rows:
        payload = _payload(row["payload"])
        if payload.get("claim_id") != claim_id:
            continue
        by = payload.get("verified_by")
        at = payload.get("verified_at")
        if isinstance(by, str) and isinstance(at, str):
            return Verification(int(row["id"]), by, at)
    return None


def effective_statuses(conn: sqlite3.Connection, claims: tuple[Claim, ...]) -> list[ClaimStatus]:
    """Each claim's effective status, in file order."""
    statuses = []
    for claim in claims:
        verification = standing_verification(conn, claim.id)
        if claim.status == "prohibited":
            statuses.append(ClaimStatus(claim.id, "prohibited", None))
        elif claim.status == "verified":
            agrees = (
                verification is not None
                and verification.verified_by == claim.verified_by
                and verification.verified_at == claim.verified_at
            )
            if agrees:
                statuses.append(ClaimStatus(claim.id, "verified", None))
            else:
                statuses.append(ClaimStatus(claim.id, "unverified", NOT_APPROVED_NOTE))
        elif verification is not None:
            note = (
                f"approved on {verification.verified_at} by {verification.verified_by};"
                " mark it verified in the claims file"
            )
            statuses.append(ClaimStatus(claim.id, "unverified", note))
        else:
            statuses.append(ClaimStatus(claim.id, "unverified", None))
    return statuses


def _claim(path: Path, index: int, entry: object) -> Claim:
    where = f"claims[{index}]"
    if not isinstance(entry, dict):
        raise ClaimsError(path, where, "must be a mapping with id, text, status and evidence")
    claim_id = entry.get("id")
    if claim_id is None or (isinstance(claim_id, str) and not claim_id.strip()):
        raise ClaimsError(path, where, "id: is missing")
    if not isinstance(claim_id, str) or not _ID.match(claim_id):
        raise ClaimsError(
            path, where, f"id: must be lower-kebab-case like service-area, got {claim_id!r}"
        )
    where = f"claims[{index}] ({claim_id})"
    text = _text(path, where, entry, "text")
    evidence = _text(path, where, entry, "evidence")
    status = entry.get("status")
    if status not in STATUSES:
        raise ClaimsError(
            path, where, f"status: must be one of {', '.join(STATUSES)}, got {status!r}"
        )
    verified_by = entry.get("verified_by")
    verified_at = _date_text(entry.get("verified_at"))
    if status == "verified":
        if not isinstance(verified_by, str) or not verified_by.strip():
            raise ClaimsError(path, where, "verified_by: a verified claim needs who verified it")
        if verified_at is None or not _is_date(verified_at):
            given = entry.get("verified_at")
            raise ClaimsError(
                path, where, f"verified_at: a verified claim needs a YYYY-MM-DD date, got {given!r}"
            )
        verified_by = verified_by.strip()
    else:
        if verified_by is not None:
            raise ClaimsError(path, where, f"verified_by: must be empty for a {status} claim")
        if entry.get("verified_at") is not None:
            raise ClaimsError(path, where, f"verified_at: must be empty for a {status} claim")
    return Claim(claim_id, text, str(status), evidence, verified_by, verified_at)


def _text(path: Path, where: str, entry: dict[object, object], field: str) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ClaimsError(path, where, f"{field}: must not be empty")
    return value.strip()


def _date_text(value: object) -> str | None:
    """YAML reads an unquoted 2026-11-30 as a date; keep the text form either way."""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _is_date(text: str) -> bool:
    if not _DATE.match(text):
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _payload(text: object) -> dict[str, object]:
    try:
        value = json.loads(str(text))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
