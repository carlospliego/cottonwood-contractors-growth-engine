# sir-target: tests/test_counted_leads_filter.py
"""COUNTED_LEADS_FILTER is qualified as leads.is_test and its comment names real users."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from cottonwood import db, review

SRC = Path(review.__file__).resolve().parent


def _comment_above_filter() -> str:
    text = (SRC / "review.py").read_text(encoding="utf-8")
    match = re.search(r"((?:^#.*\n)+)COUNTED_LEADS_FILTER = ", text, re.M)
    assert match is not None
    return " ".join(line.lstrip("# ") for line in match.group(1).splitlines())


def test_filter_names_the_leads_column() -> None:
    assert review.COUNTED_LEADS_FILTER.startswith("leads.is_test")


def test_comment_claims_only_users_that_exist() -> None:
    comment = _comment_above_filter()
    assert "report.py" in comment
    assert "leads.is_test" in comment
    report = (SRC / "report.py").read_text(encoding="utf-8")
    assert "review.COUNTED_LEADS_FILTER" in report


def test_filter_is_unambiguous_in_a_join_with_another_is_test_column(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        conn.execute("CREATE TEMP TABLE other (lead_id INTEGER, is_test INTEGER)")
        sql = (
            "SELECT count(*) FROM leads JOIN other ON other.lead_id = leads.id"
            f" WHERE {review.COUNTED_LEADS_FILTER}"
        )
        assert conn.execute(sql).fetchone()[0] == 0
    except sqlite3.OperationalError as exc:  # pragma: no cover - the failure being guarded
        raise AssertionError(f"filter is ambiguous in a join: {exc}") from None
    finally:
        conn.close()
