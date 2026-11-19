"""A lead's newest evidence by its effective date (R-10).

An evidence item's effective date is the day its source was published when that is known,
else the day it was observed. Evidence age is measured from that date, so an old article read
today is not counted as fresh.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

PUBLISHED = "published"
OBSERVED = "observed"


@dataclass(frozen=True)
class NewestEvidence:
    """The lead's newest evidence: its URL, effective date text and which date that is."""

    url: str
    date: str
    basis: str  # PUBLISHED or OBSERVED


def newest(conn: sqlite3.Connection, lead_id: int) -> NewestEvidence | None:
    """The evidence with the latest effective date (ties: highest id), or None if there is none."""
    row = conn.execute(
        "SELECT url,"
        " CASE WHEN published_at IS NOT NULL AND trim(published_at) <> ''"
        "  THEN substr(trim(published_at), 1, 10) ELSE substr(trim(observed_at), 1, 10)"
        " END AS effective,"
        " CASE WHEN published_at IS NOT NULL AND trim(published_at) <> ''"
        f"  THEN '{PUBLISHED}' ELSE '{OBSERVED}' END AS basis"
        " FROM evidence WHERE lead_id = ?"
        " ORDER BY effective DESC, id DESC LIMIT 1",
        (lead_id,),
    ).fetchone()
    if row is None:
        return None
    return NewestEvidence(url=str(row["url"]), date=str(row["effective"]), basis=str(row["basis"]))
