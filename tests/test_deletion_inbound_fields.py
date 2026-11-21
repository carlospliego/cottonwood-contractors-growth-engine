# sir-target: tests/test_deletion_inbound_fields.py
"""A deletion request also clears the inbound scope and a buyer-stated budget (R-35, CCGE-032)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, deletion, inbound

RUNBOOK = Path(__file__).resolve().parent.parent / "docs" / "runbook.md"
NOW = "2026-11-20T10:00:00Z"


def _deletion_section() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    match = re.search(r"^## Deletion requests\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, "runbook has no '## Deletion requests' section"
    return match.group(1)


def _lead_clearing_sql() -> str:
    blocks = [b for b in re.findall(r"```sql\n(.*?)```", _deletion_section(), re.S)]
    leads = [b for b in blocks if "UPDATE leads" in b]
    assert len(leads) == 1, f"expected one lead-clearing SQL block, found {len(leads)}"
    return str(leads[0])


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _log_inquiry(db_path: Path) -> tuple[int, int]:
    """Log an inquiry with a scope and a stated budget; return (contact_id, lead_id)."""
    inquiry = inbound.validate(
        inbound.RawInquiry(
            channel="form",
            received="2026-11-16 09:30",
            segment="commercial",
            name="Pat Lee",
            email="pat@example.com",
            company="Acme Builders",
            location="Pat's warehouse on 5th",
            scope="Re-roof Pat's warehouse",
            budget="45000",
        )
    )
    conn = db.connect(db_path)
    try:
        lead_id = inbound.log_inquiry(conn, inquiry)
        row = conn.execute("SELECT contact_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return int(row["contact_id"]), lead_id
    finally:
        conn.close()


def _lead(db_path: Path, lead_id: int) -> sqlite3.Row:
    conn = db.connect(db_path)
    try:
        row: sqlite3.Row | None = conn.execute(
            "SELECT hypothesis, next_action, property_location, project_scope,"
            " value_amount, value_basis FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


def _assert_cleared(row: sqlite3.Row) -> None:
    for column in (
        "hypothesis",
        "next_action",
        "property_location",
        "project_scope",
        "value_amount",
        "value_basis",
    ):
        assert row[column] is None, column


def test_runbook_lead_step_names_every_column() -> None:
    sql = " ".join(_lead_clearing_sql().split())
    for assignment in (
        "hypothesis = NULL",
        "next_action = NULL",
        "property_location = NULL",
        "project_scope = NULL",
        "value_amount = NULL",
        "value_basis = NULL",
    ):
        assert assignment in sql, assignment
    assert "value_basis = 'buyer-stated'" in sql


def test_runbook_lead_sql_clears_scope_and_stated_budget(db_path: Path) -> None:
    contact_id, lead_id = _log_inquiry(db_path)
    before = _lead(db_path, lead_id)
    assert before["project_scope"] == "Re-roof Pat's warehouse"
    assert before["value_amount"] == "45000"
    assert before["value_basis"] == inbound.BUDGET_BASIS

    sql = _lead_clearing_sql().replace("contact_id = 42", f"contact_id = {contact_id}")
    conn = db.connect(db_path)
    try:
        conn.executescript(sql)
    finally:
        conn.close()
    _assert_cleared(_lead(db_path, lead_id))


def test_deletion_request_command_clears_the_same_columns(db_path: Path) -> None:
    contact_id, lead_id = _log_inquiry(db_path)
    conn = db.connect(db_path)
    try:
        deletion.delete_contact(conn, contact_id, "founder", NOW)
    finally:
        conn.close()
    _assert_cleared(_lead(db_path, lead_id))


def test_a_value_we_estimated_ourselves_is_kept(db_path: Path) -> None:
    contact_id, lead_id = _log_inquiry(db_path)
    conn = db.connect(db_path)
    try:
        conn.execute(
            "UPDATE leads SET value_amount = '60000', value_basis = 'estimated' WHERE id = ?",
            (lead_id,),
        )
        conn.commit()
        deletion.delete_contact(conn, contact_id, "founder", NOW)
    finally:
        conn.close()
    row = _lead(db_path, lead_id)
    assert row["project_scope"] is None
    assert (row["value_amount"], row["value_basis"]) == ("60000", "estimated")
