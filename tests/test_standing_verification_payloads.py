# sir-target: tests/test_standing_verification_payloads.py
"""standing_verification skips other claims' rows and malformed payloads (R-19).

F-testing-4: the loop that skips a claim_verified row for another claim id, or one whose payload
lacks a string verified_by and verified_at, had no test, so a change that returned the first
row it saw would pass the suite.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from cottonwood import claims, db

STAMP = "2026-11-30T07:00:00Z"
VALID = {
    "claim_id": "service-area",
    "approval_activity_id": 1,
    "verified_by": "Founder",
    "verified_at": "2026-11-30",
}
NOISE = [
    json.dumps({**VALID, "claim_id": "other-claim", "verified_by": "Someone Else"}),
    json.dumps({"claim_id": "service-area"}),  # no verifier and no date
    json.dumps({**VALID, "verified_by": None}),  # a date but no verifier
    json.dumps({**VALID, "verified_at": 20261130}),  # date is not a string
    json.dumps(["service-area", "Founder", "2026-11-30"]),  # not an object
]


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    connection = db.connect(path)
    try:
        yield connection
    finally:
        connection.close()


def _insert(conn: sqlite3.Connection, payload: str) -> int:
    cursor = conn.execute(
        "INSERT INTO activities (lead_id, contact_id, type, payload, actor, occurred_at,"
        " recorded_at, voids_activity_id) VALUES (NULL, NULL, ?, ?, 'founder', ?, ?, NULL)",
        (claims.CLAIM_VERIFIED_TYPE, payload, STAMP, STAMP),
    )
    conn.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def test_the_valid_row_is_found_past_later_rows_it_must_skip(conn: sqlite3.Connection) -> None:
    valid_id = _insert(conn, json.dumps(VALID))
    for payload in NOISE:  # every row to skip is newer, so it is read first
        _insert(conn, payload)
    found = claims.standing_verification(conn, "service-area")
    assert found == claims.Verification(valid_id, "Founder", "2026-11-30")


def test_only_rows_to_skip_give_no_standing_verification(conn: sqlite3.Connection) -> None:
    for payload in NOISE:
        _insert(conn, payload)
    assert claims.standing_verification(conn, "service-area") is None


def test_the_other_claim_row_still_counts_for_its_own_claim(conn: sqlite3.Connection) -> None:
    for payload in NOISE:
        _insert(conn, payload)
    found = claims.standing_verification(conn, "other-claim")
    assert found is not None
    assert (found.verified_by, found.verified_at) == ("Someone Else", "2026-11-30")
