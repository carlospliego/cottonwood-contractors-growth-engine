# sir-target: tests/test_inbound_counts_breakdown.py
"""inbound_counts: an unknown channel or segment is in total but not in a breakdown."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from cottonwood import db, inbound, review


def _log(conn: sqlite3.Connection, channel: str, segment: str) -> None:
    raw = inbound.RawInquiry(
        channel=channel, received="2026-11-16 09:30", segment=segment, name="Pat Lee"
    )
    inbound.log_inquiry(conn, inbound.validate(raw))


def test_the_documented_gap_between_total_and_the_breakdowns(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        _log(conn, "form", "commercial")
        _log(conn, "phone", "residential")
        # A value log-inbound cannot write, as a hand edit or an old import might leave it.
        conn.execute("UPDATE leads SET channel = 'email', segment = 'industrial' WHERE id = 2")
        conn.commit()
        counts = review.inbound_counts(conn)
    finally:
        conn.close()
    assert counts.total == 2
    assert sum(counts.by_channel.values()) == 1
    assert sum(counts.by_segment.values()) == 1
    assert set(counts.by_channel) == set(inbound.CHANNELS)
    assert set(counts.by_segment) == set(inbound.SEGMENTS)


def test_the_docstrings_say_the_breakdowns_may_not_sum() -> None:
    cls_doc = " ".join((review.InboundCounts.__doc__ or "").split())
    fn_doc = " ".join((review.inbound_counts.__doc__ or "").split())
    assert "the breakdowns can sum to less" in cls_doc
    assert "may not sum to it" in fn_doc
