# sir-target: tests/test_lead_type_bound.py
"""The inquiry lead type lives in inbound.LEAD_TYPE and every query binds it (F-maint-4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db, inbound, review

SRC = Path(inbound.__file__).resolve().parent


def test_lead_type_constant() -> None:
    assert inbound.LEAD_TYPE == "inbound_inquiry"


@pytest.mark.parametrize("module", ["inbound.py", "review.py", "report.py"])
def test_no_query_spells_the_type_out(module: str) -> None:
    text = (SRC / module).read_text(encoding="utf-8")
    assert "'inbound_inquiry'" not in text
    assert "type = 'inbound" not in text


def test_logged_inquiries_are_found_by_the_bound_queries(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        for name, email, is_test in [("Pat", "pat@example.com", False), ("Sam", None, True)]:
            raw = inbound.RawInquiry(
                channel="form",
                received="2026-11-16 09:30",
                segment="commercial",
                name=name,
                email=email,
                is_test=is_test,
            )
            inbound.log_inquiry(conn, inbound.validate(raw))
        stored = {str(r[0]) for r in conn.execute("SELECT type FROM leads")}
        rows = review.inbound_rows(conn)
        counts = review.inbound_counts(conn)
        dupes = inbound.find_same_day_duplicates(
            conn, "pat@example.com", None, "2026-11-16T16:30:00Z"
        )
    finally:
        conn.close()
    assert stored == {inbound.LEAD_TYPE}
    assert len(rows) == 2
    assert (counts.total, counts.tests_excluded) == (1, 1)
    assert len(dupes) == 1
