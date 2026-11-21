"""Tests for log-inbound: recording only what the inquirer supplied (R-1, R-3)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

LATEST_VERSION = len(db.discover_migrations())
TABLES = ("leads", "contacts", "organizations", "activities")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _log(db_path: Path, *args: str) -> int:
    return main(["log-inbound", "--db", str(db_path), *args])


def _rows(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    conn = db.connect(db_path)
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


def _counts(db_path: Path) -> dict[str, int]:
    return {t: _rows(db_path, f"SELECT count(*) FROM {t}")[0][0] for t in TABLES}


BASIC = (
    "--channel",
    "form",
    "--received",
    "2026-11-16 09:30",
    "--segment",
    "commercial",
    "--name",
    "Pat Lee",
    "--email",
    "Pat@Example.com",
)


def test_migrate_adds_nullable_project_scope(db_path: Path) -> None:
    conn = db.connect(db_path)
    try:
        assert db.user_version(conn) == LATEST_VERSION
        columns = {row["name"]: row for row in conn.execute("PRAGMA table_info(leads)")}
    finally:
        conn.close()
    assert "project_scope" in columns
    assert columns["project_scope"]["notnull"] == 0


def test_basic_form_inquiry_stores_only_supplied_fields(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _log(db_path, *BASIC) == EXIT_OK

    leads = _rows(db_path, "SELECT * FROM leads")
    assert len(leads) == 1
    lead = leads[0]
    assert lead["type"] == "inbound_inquiry"
    assert lead["stage"] == "candidate"
    assert lead["channel"] == "form"
    assert lead["segment"] == "commercial"
    assert lead["received_at"] == "2026-11-16T16:30:00Z"
    assert lead["is_test"] == 0
    for column in ("project_scope", "value_amount", "value_basis", "property_location"):
        assert lead[column] is None, column
    assert lead["organization_id"] is None

    contact = _rows(db_path, "SELECT * FROM contacts WHERE id = ?", (lead["contact_id"],))[0]
    assert contact["name"] == "Pat Lee"
    assert contact["email"] == "Pat@Example.com"
    assert contact["email_norm"] == "pat@example.com"
    assert contact["phone_e164"] is None

    out = capsys.readouterr().out
    assert f"logged inquiry lead {lead['id']}" in out
    assert "2026-11-16 09:30 -07:00" in out
    assert "TEST" not in out


FULL = (
    "--channel",
    "phone",
    "--received",
    "2026-11-16 10:00",
    "--segment",
    "residential",
    "--phone",
    "(801) 555-0134",
    "--scope",
    "lobby refresh",
    "--budget",
    "25000",
    "--location",
    "Murray, UT",
    "--company",
    "Acme Holdings",
)


def test_all_supplied_fields_are_stored_and_organization_reused(db_path: Path) -> None:
    assert _log(db_path, *FULL) == EXIT_OK
    lead = _rows(db_path, "SELECT * FROM leads")[0]
    assert lead["project_scope"] == "lobby refresh"
    assert lead["value_amount"] == "25000"
    assert lead["value_basis"] == "buyer-stated"
    assert lead["property_location"] == "Murray, UT"
    org = _rows(db_path, "SELECT * FROM organizations WHERE id = ?", (lead["organization_id"],))
    assert org[0]["name"] == "Acme Holdings"
    contact = _rows(db_path, "SELECT * FROM contacts WHERE id = ?", (lead["contact_id"],))[0]
    assert contact["phone_e164"] == "+18015550134"

    second = [
        "--channel",
        "form",
        "--received",
        "2026-11-18 10:00",
        "--segment",
        "commercial",
        "--name",
        "Sam",
        "--company",
        "ACME holdings",
    ]
    assert _log(db_path, *second) == EXIT_OK
    org_ids = [r[0] for r in _rows(db_path, "SELECT organization_id FROM leads ORDER BY id")]
    assert org_ids == [lead["organization_id"], lead["organization_id"]]
    assert _counts(db_path)["organizations"] == 1


def test_one_inquiry_logged_activity_without_personal_data(db_path: Path) -> None:
    assert _log(db_path, *FULL, "--name", "Pat Lee", "--email", "pat@example.com") == EXIT_OK
    lead = _rows(db_path, "SELECT * FROM leads")[0]
    activities = _rows(db_path, "SELECT * FROM activities")
    assert len(activities) == 1
    activity = activities[0]
    assert activity["lead_id"] == lead["id"]
    assert activity["type"] == "inquiry_logged"
    assert activity["occurred_at"] == lead["received_at"]
    payload = json.loads(activity["payload"])
    assert payload["channel"] == "phone"
    assert payload["segment"] == "residential"
    assert payload["is_test"] is False
    text = activity["payload"]
    for value in ("Pat Lee", "pat@example.com", "801", "555", "lobby refresh", "25000"):
        assert value not in text, value


def test_received_accepts_utc_z(db_path: Path) -> None:
    args = list(BASIC)
    args[3] = "2026-11-16T16:30:00Z"
    assert _log(db_path, *args) == EXIT_OK
    assert _rows(db_path, "SELECT received_at FROM leads")[0][0] == "2026-11-16T16:30:00Z"


@pytest.mark.parametrize(
    "drop_or_replace",
    [
        ("--received", None),
        ("--channel", None),
        ("--segment", None),
        ("--channel", "email"),
        ("--segment", "industrial"),
    ],
)
def test_missing_or_invalid_required_options_exit_nonzero(
    db_path: Path, drop_or_replace: tuple[str, str | None]
) -> None:
    flag, replacement = drop_or_replace
    args = list(BASIC)
    i = args.index(flag)
    if replacement is None:
        del args[i : i + 2]
    else:
        args[i + 1] = replacement
    assert _log(db_path, *args) != EXIT_OK
    assert _counts(db_path)["leads"] == 0


@pytest.mark.parametrize(
    ("args", "field"),
    [
        (["--email", "not-an-email"], "email"),
        (["--phone", "12345"], "phone"),
        (["--name", "Pat", "--budget", "abc"], "budget"),
        (["--name", "Pat", "--budget", "-5"], "budget"),
        (["--name", "Pat", "--budget", "NaN"], "budget"),
        (["--name", "   "], "name/email/phone"),
        ([], "name/email/phone"),
    ],
)
def test_invalid_fields_exit_1_naming_the_field_and_write_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str], args: list[str], field: str
) -> None:
    base = ["--channel", "form", "--received", "2026-11-16 09:30", "--segment", "unknown"]
    assert _log(db_path, *base, *args) == EXIT_REFUSED
    assert field in capsys.readouterr().err
    assert _counts(db_path) == dict.fromkeys(TABLES, 0)


@pytest.mark.parametrize("received", ["yesterday", "2026-11-16", "2026-02-30 09:00", "16:30Z"])
def test_unparseable_received_exits_1(
    db_path: Path, capsys: pytest.CaptureFixture[str], received: str
) -> None:
    args = ["--channel", "form", "--received", received, "--segment", "unknown", "--name", "P"]
    assert _log(db_path, *args) == EXIT_REFUSED
    assert "received" in capsys.readouterr().err
    assert _counts(db_path) == dict.fromkeys(TABLES, 0)


def test_test_flag_labels_the_inquiry(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _log(db_path, *BASIC, "--test") == EXIT_OK
    assert _rows(db_path, "SELECT is_test FROM leads")[0][0] == 1
    assert "TEST" in capsys.readouterr().out


def test_blank_optional_fields_are_stored_as_null(db_path: Path) -> None:
    assert _log(db_path, *BASIC, "--scope", "  ", "--company", "", "--location", " ") == EXIT_OK
    lead = _rows(db_path, "SELECT * FROM leads")[0]
    assert lead["project_scope"] is None
    assert lead["property_location"] is None
    assert lead["organization_id"] is None


def test_missing_database_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope.db"
    assert _log(missing, *BASIC) == EXIT_REFUSED
    assert "error" in capsys.readouterr().err
    assert not missing.exists()


def test_parse_received_local_and_utc() -> None:
    assert timeutil.parse_received("2026-07-01 09:00") == "2026-07-01T15:00:00Z"
    assert timeutil.parse_received("2026-11-16T16:30:00.5+00:00") == "2026-11-16T16:30:00Z"
    with pytest.raises(ValueError):
        timeutil.parse_received("2026-11-16T09:30:00-07:00")
