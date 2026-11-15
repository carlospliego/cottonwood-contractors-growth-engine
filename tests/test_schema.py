"""Tests for the 002_core schema: tables, columns, R-14 stages, append-only triggers, keys."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import EXIT_OK, main

NOW = "2026-11-15T10:00:00Z"

KEY_COLUMNS: dict[str, set[str]] = {
    "organizations": {"id", "name", "name_norm", "domain_norm", "type", "category", "created_at"},
    "contacts": {
        "id",
        "organization_id",
        "name",
        "email",
        "email_norm",
        "phone_e164",
        "role",
        "source_url",
        "eligibility",
        "deleted_at",
    },
    "leads": {
        "id",
        "type",
        "organization_id",
        "contact_id",
        "stage",
        "segment",
        "channel",
        "property_location",
        "hypothesis",
        "next_action",
        "founder_time_h",
        "value_amount",
        "value_basis",
        "referred_by",
        "is_test",
        "received_at",
    },
    "evidence": {
        "id",
        "lead_id",
        "url",
        "observed_at",
        "published_at",
        "excerpt",
        "kind",
        "source_status",
    },
    "activities": {
        "id",
        "lead_id",
        "contact_id",
        "type",
        "payload",
        "actor",
        "occurred_at",
        "recorded_at",
        "voids_activity_id",
    },
    "agent_runs": {
        "id",
        "skill",
        "skill_version",
        "model",
        "started_at",
        "ended_at",
        "input_ref",
        "output_ref",
        "validation",
        "tokens",
        "cost_usd",
        "cost_source",
        "cost_estimated",
    },
    "suppression": {"email_norm", "reason", "source", "added_at"},
}

# R-14 (docs/cottonwood-growth-engine.md).
DIRECT_STAGES = [
    "candidate",
    "researched",
    "contacted_or_replied",
    "buyer_need_confirmed",
    "walkthrough",
    "proposal",
    "won",
    "lost",
    "closed_no_fit",
]
RELATIONSHIP_STAGES = [
    "identified",
    "researched",
    "introduced",
    "responded",
    "active_relationship",
    "closed_no_fit",
]
ALLOWED_PAIRS = (
    [("inbound_inquiry", stage) for stage in DIRECT_STAGES]
    + [("direct_candidate", stage) for stage in DIRECT_STAGES]
    + [("relationship_prospect", stage) for stage in RELATIONSHIP_STAGES]
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "schema.db"
    db.migrate(path)
    return path


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = db.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def _tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        " ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _insert_activity(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO activities (type, payload, actor, occurred_at, recorded_at)"
        " VALUES ('inquiry_logged', '{\"note\": \"first\"}', 'founder', ?, ?)",
        (NOW, NOW),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _activity(conn: sqlite3.Connection, activity_id: int) -> tuple[object, ...]:
    row = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    return tuple(row)


def test_migrate_on_new_file_gives_version_2_and_exactly_the_core_tables(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "fresh.db"

    assert main(["migrate", "--db", str(path)]) == EXIT_OK

    assert "at version 2" in capsys.readouterr().out
    conn = db.connect(path)
    try:
        assert db.user_version(conn) == 2
        assert _tables(conn) == sorted(KEY_COLUMNS)
    finally:
        conn.close()


@pytest.mark.parametrize("table", sorted(KEY_COLUMNS))
def test_table_has_key_columns(conn: sqlite3.Connection, table: str) -> None:
    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}
    assert KEY_COLUMNS[table] <= columns


def test_activity_update_is_rejected_and_row_unchanged(conn: sqlite3.Connection) -> None:
    activity_id = _insert_activity(conn)
    before = _activity(conn, activity_id)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE activities SET actor = 'someone' WHERE id = ?", (activity_id,))
    conn.rollback()

    assert _activity(conn, activity_id) == before


def test_activity_delete_is_rejected_and_row_unchanged(conn: sqlite3.Connection) -> None:
    activity_id = _insert_activity(conn)
    before = _activity(conn, activity_id)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    conn.rollback()

    assert _activity(conn, activity_id) == before


def test_activity_payload_must_be_json(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO activities (type, payload, actor, occurred_at, recorded_at)"
            " VALUES ('inquiry_logged', 'not json', 'founder', ?, ?)",
            (NOW, NOW),
        )


def _insert_suppression(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO suppression (email_norm, reason, source, added_at)"
        " VALUES ('jane@example.com', 'opt_out', 'reply', ?)",
        (NOW,),
    )
    conn.commit()


def _suppression_rows(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return [tuple(row) for row in conn.execute("SELECT * FROM suppression")]


def test_suppression_delete_is_rejected_and_row_kept(conn: sqlite3.Connection) -> None:
    _insert_suppression(conn)

    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM suppression WHERE email_norm = 'jane@example.com'")
    conn.rollback()

    assert _suppression_rows(conn) == [("jane@example.com", "opt_out", "reply", NOW)]


def test_suppression_update_is_rejected_and_row_unchanged(conn: sqlite3.Connection) -> None:
    _insert_suppression(conn)

    with pytest.raises(sqlite3.IntegrityError, match="never deleted or changed"):
        conn.execute("UPDATE suppression SET reason = 'mistake'")
    conn.rollback()

    assert _suppression_rows(conn) == [("jane@example.com", "opt_out", "reply", NOW)]


@pytest.mark.parametrize(("lead_type", "stage"), ALLOWED_PAIRS)
def test_allowed_type_stage_pair_inserts(
    conn: sqlite3.Connection, lead_type: str, stage: str
) -> None:
    conn.execute("INSERT INTO leads (type, stage) VALUES (?, ?)", (lead_type, stage))
    conn.commit()
    row = conn.execute("SELECT type, stage FROM leads").fetchone()
    assert (row["type"], row["stage"]) == (lead_type, stage)


@pytest.mark.parametrize(
    ("lead_type", "stage"),
    [
        ("relationship_prospect", "walkthrough"),
        ("direct_candidate", "introduced"),
        ("inbound_inquiry", "active_relationship"),
        ("direct_candidate", "unknown_stage"),
        ("partner", "candidate"),
    ],
)
def test_disallowed_type_stage_pair_is_rejected(
    conn: sqlite3.Connection, lead_type: str, stage: str
) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("INSERT INTO leads (type, stage) VALUES (?, ?)", (lead_type, stage))
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_is_test_must_be_0_or_1(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO leads (type, stage, is_test) VALUES ('direct_candidate', 'candidate', 2)"
        )


def test_eligibility_and_evidence_kind_are_checked(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("INSERT INTO contacts (name, eligibility) VALUES ('Jane', 'maybe')")
    conn.execute("INSERT INTO leads (id, type, stage) VALUES (1, 'direct_candidate', 'candidate')")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute(
            "INSERT INTO evidence (lead_id, url, observed_at, kind)"
            " VALUES (1, 'https://example.com', ?, 'rumor')",
            (NOW,),
        )


def test_contact_eligibility_defaults_to_unknown(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO contacts (name) VALUES ('Jane')")
    assert conn.execute("SELECT eligibility FROM contacts").fetchone()[0] == "unknown"


def test_domain_norm_is_unique_when_set(conn: sqlite3.Connection) -> None:
    insert = (
        "INSERT INTO organizations (name, name_norm, domain_norm, created_at) VALUES (?, ?, ?, ?)"
    )
    conn.execute(insert, ("A", "a", None, NOW))
    conn.execute(insert, ("B", "b", None, NOW))
    conn.execute(insert, ("C", "c", "example.com", NOW))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(insert, ("D", "d", "example.com", NOW))


def _make_version_1(path: Path) -> None:
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 1")
    raw.close()


def test_version_1_database_upgrades_to_2_then_applies_nothing(tmp_path: Path) -> None:
    path = tmp_path / "v1.db"
    _make_version_1(path)

    first = db.migrate(path)
    second = db.migrate(path)

    assert (first.from_version, first.to_version) == (1, 2)
    assert [m.path.name for m in first.applied] == ["002_core.sql"]
    assert (second.from_version, second.to_version) == (2, 2)
    assert second.applied == ()


def test_migrate_command_on_version_1_reports_applied_then_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "v1-cli.db"
    _make_version_1(path)

    assert main(["migrate", "--db", str(path)]) == EXIT_OK
    assert "at version 2 (applied 1)" in capsys.readouterr().out
    assert main(["migrate", "--db", str(path)]) == EXIT_OK
    assert "at version 2 (applied 0)" in capsys.readouterr().out


def test_connect_turns_foreign_keys_on(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_contact_with_missing_organization_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute("INSERT INTO contacts (organization_id, name) VALUES (999, 'Jane')")
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0


def test_connect_returns_rows_by_name(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT 1 AS one").fetchone()
    assert row["one"] == 1


def test_connect_refuses_a_missing_file_and_creates_nothing(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"

    with pytest.raises(db.DatabaseMissingError, match="database does not exist"):
        db.connect(path)

    assert not path.exists()
