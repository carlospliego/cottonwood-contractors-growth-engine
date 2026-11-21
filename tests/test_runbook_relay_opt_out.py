# sir-target: tests/test_runbook_relay_opt_out.py
"""The relay opt-out SQL stores a normalized email_norm and says it must be (F-correctness-7)."""

from __future__ import annotations

import re
from pathlib import Path

from cottonwood import db, eligibility
from cottonwood.normalize import normalize_email

RUNBOOK = Path(__file__).resolve().parent.parent / "docs" / "runbook.md"


def _relay_section() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    match = re.search(r"^## Relay\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, "runbook has no '## Relay' section"
    return match.group(1)


def _opt_out_sql() -> str:
    blocks = [
        b for b in re.findall(r"```sql\n(.*?)```", _relay_section(), re.S) if "suppression" in b
    ]
    assert len(blocks) == 1, blocks
    return str(blocks[0])


def test_the_text_says_email_norm_is_trimmed_and_lower_cased() -> None:
    prose = " ".join(_relay_section().split())
    assert "`email_norm` must be the trimmed, lower-cased address" in prose


def test_the_example_normalizes_in_sql() -> None:
    assert "lower(trim(" in _opt_out_sql()


def test_running_the_example_suppresses_the_normalized_address(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        conn.executescript(_opt_out_sql())
        stored = [str(r[0]) for r in conn.execute("SELECT email_norm FROM suppression")]
    finally:
        conn.close()
    assert stored == [normalize_email(" Pat@Example.com ")] == ["pat@example.com"]


def test_eligibility_sees_it_for_the_mixed_case_contact(tmp_path: Path) -> None:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    conn = db.connect(path)
    try:
        conn.executescript(_opt_out_sql())
        assert eligibility._is_suppressed(conn, normalize_email("PAT@example.COM"))
    finally:
        conn.close()
