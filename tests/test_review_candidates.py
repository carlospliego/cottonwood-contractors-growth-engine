"""Tests for the review's candidate queues: checklist, evidence age, order, hand review (R-13)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cottonwood import config, db, review, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today: 2026-11-30
ORDER = (
    "Order: most yes answers first; ties: lower founder time first (unknown last);"
    " then lowest lead id."
)
CONFIG_WITH_AGE = """\
paths:
  backup_dir: data/backups
review:
  max_evidence_age_days: 30
  checklists:
    direct_candidate:
      - key: direct_signal
        label: Current, directly sourced signal
      - key: decision_maker
        label: Decision maker identified
      - key: fit
        label: Fits the service area
    relationship_prospect:
      - key: shared_clients
        label: Serves the same clients
"""
CONFIG_NO_AGE = CONFIG_WITH_AGE.replace("  max_evidence_age_days: 30\n", "")
DIRECT_KEYS = ("direct_signal", "decision_maker", "fit")
STAGES = {
    "direct_candidate": "researched",
    "relationship_prospect": "researched",
    "inbound_inquiry": "candidate",
}


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pilot.yaml"
    path.write_text(CONFIG_WITH_AGE, encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    return path


@pytest.fixture
def db_path(tmp_path: Path, config_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _exec(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def _lead(
    db_path: Path,
    lead_type: str = "direct_candidate",
    answers: dict[str, str] | None = None,
    founder_time: float | None = None,
    next_action: str | None = None,
    organization: str | None = None,
    contact: str | None = None,
    is_test: bool = False,
) -> int:
    org_id = None
    if organization is not None:
        org_id = _exec(
            db_path,
            "INSERT INTO organizations (name, name_norm, created_at) VALUES (?, ?, ?)",
            (organization, organization.lower(), NOW),
        )
    contact_id = None
    if contact is not None:
        contact_id = _exec(
            db_path,
            "INSERT INTO contacts (organization_id, name, eligibility) VALUES (?, ?, 'eligible')",
            (org_id, contact),
        )
    return _exec(
        db_path,
        "INSERT INTO leads (type, stage, organization_id, contact_id, checklist, founder_time_h,"
        " next_action, is_test) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            lead_type,
            STAGES[lead_type],
            org_id,
            contact_id,
            json.dumps(answers) if answers is not None else None,
            founder_time,
            next_action,
            int(is_test),
        ),
    )


def _evidence(db_path: Path, lead: int, url: str, observed: str) -> None:
    _exec(
        db_path,
        "INSERT INTO evidence (lead_id, url, observed_at, kind) VALUES (?, ?, ?, 'fact')",
        (lead, url, observed),
    )


def _review(db_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> str:
    capsys.readouterr()
    assert main(["review", "--db", str(db_path), *args]) == EXIT_OK
    return capsys.readouterr().out


def _section(text: str, title: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(f"## {title}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def _table(section: list[str]) -> tuple[list[str], list[list[str]]]:
    rows = [line for line in section if line.startswith("| ")]
    split = [[cell.strip() for cell in row.strip("|").split(" | ")] for row in rows]
    return split[0], split[1:]


def _yes(count: int) -> dict[str, str]:
    return {key: ("yes" if i < count else "no") for i, key in enumerate(DIRECT_KEYS)}


# --- AC 1: sections in order, inbound unchanged, order line ------------------------------


def test_sections_follow_the_unchanged_inbound_section(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "log-inbound",
                "--channel",
                "phone",
                "--received",
                "2026-11-16 09:30",
                "--segment",
                "residential",
                "--phone",
                "801-555-0134",
                "--db",
                str(db_path),
            ]
        )
        == EXIT_OK
    )
    _lead(db_path, answers=_yes(1))

    text = _review(db_path, capsys)

    lines = text.splitlines()
    inbound_at = lines.index("## Inbound inquiries")
    direct_at = lines.index("## Direct candidates")
    partner_at = lines.index("## Relationship prospects")
    assert inbound_at < direct_at < partner_at
    conn = db.connect(db_path)
    try:
        expected_inbound = review._inbound_section(conn, NOW)
    finally:
        conn.close()
    assert lines[: direct_at - 1] == expected_inbound
    assert lines[direct_at - 1] == ""
    assert ORDER in _section(text, "Direct candidates")
    assert ORDER in _section(text, "Relationship prospects")


def test_render_review_without_config_keeps_the_inbound_output(db_path: Path) -> None:
    conn = db.connect(db_path)
    try:
        text = review.render_review(conn, NOW)
    finally:
        conn.close()
    assert text.startswith("# Review\n")
    assert "No direct candidates." in text
    assert "No relationship prospects." in text
    assert text.endswith("No relationship prospects.\n")


# --- AC 2: header, unknown answers, yes count, hand review, TEST --------------------------


def test_direct_table_columns_answers_and_labels(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reviewed = _lead(
        db_path,
        answers={"direct_signal": "yes", "fit": "yes"},
        founder_time=1.5,
        next_action="Call the GC",
        organization="Acme Builders",
        contact="Pat Lee",
    )
    _lead(db_path, answers=None, is_test=True)
    assert (
        main(
            [
                "mark-reviewed",
                str(reviewed),
                "relevant",
                "--reviewer",
                "founder",
                "--db",
                str(db_path),
            ]
        )
        == EXIT_OK
    )

    header, rows = _table(_section(_review(db_path, capsys), "Direct candidates"))

    assert header == [
        "Lead",
        "Organization",
        "Contact",
        "Reach",
        "Eligibility",
        *DIRECT_KEYS,
        "Yes",
        "Evidence URL",
        "Evidence age (days)",
        "Next action",
        "Founder time (h)",
        "Hand review",
        "Label",
    ]
    first, second = rows
    assert first[:5] == [str(reviewed), "Acme Builders", "Pat Lee", "none", "eligible"]
    assert first[5:8] == ["yes", "unknown", "yes"]
    assert first[8] == "2"
    assert first[11:14] == ["Call the GC", "1.5", "relevant"]
    assert first[14] == ""
    assert second[5:8] == ["unknown", "unknown", "unknown"]
    assert second[8] == "0"
    assert second[13] == "—"
    assert second[14] == "TEST"


def test_replaced_review_shows_the_new_result(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path, answers=_yes(1))
    base = ["mark-reviewed", str(lead), "--reviewer", "founder", "--db", str(db_path)]
    assert main([*base[:2], "relevant", *base[2:]]) == EXIT_OK
    assert main([*base[:2], "fabricated", *base[2:], "--replace"]) == EXIT_OK

    _, rows = _table(_section(_review(db_path, capsys), "Direct candidates"))

    assert rows[0][13] == "fabricated"


# --- AC 3: order --------------------------------------------------------------------------


def test_order_by_yes_then_founder_time_unknown_last_then_id(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    two_slow = _lead(db_path, answers=_yes(2), founder_time=1.5)
    three = _lead(db_path, answers=_yes(3), founder_time=4)
    two_fast = _lead(db_path, answers=_yes(2), founder_time=0.5)
    two_unknown = _lead(db_path, answers=_yes(2))

    _, rows = _table(_section(_review(db_path, capsys), "Direct candidates"))

    assert [row[0] for row in rows] == [
        str(three),
        str(two_fast),
        str(two_slow),
        str(two_unknown),
    ]


def test_equal_yes_and_time_fall_back_to_lowest_lead_id(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _lead(db_path, answers=_yes(1), founder_time=2)
    second = _lead(db_path, answers=_yes(1), founder_time=2)
    _, rows = _table(_section(_review(db_path, capsys), "Direct candidates"))
    assert [row[0] for row in rows] == [str(first), str(second)]


# --- AC 4: newest evidence and its age ----------------------------------------------------


def test_newest_evidence_and_age_over_the_max(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stale = _lead(db_path, answers=_yes(3))
    _evidence(db_path, stale, "https://acme.example/old", "2026-10-01")
    _evidence(db_path, stale, "https://acme.example/new", "2026-10-30")
    fresh = _lead(db_path, answers=_yes(2))
    _evidence(db_path, fresh, "https://beta.example/post", "2026-10-31")

    section = _section(_review(db_path, capsys), "Direct candidates")

    assert "Max evidence age: 30 days" in section
    _, rows = _table(section)
    by_lead = {row[0]: row for row in rows}
    assert by_lead[str(stale)][9:11] == ["https://acme.example/new", "31 (over 30)"]
    assert by_lead[str(fresh)][9:11] == ["https://beta.example/post", "30"]


def test_without_max_age_plain_days(
    db_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path.write_text(CONFIG_NO_AGE, encoding="utf-8")
    lead = _lead(db_path, answers=_yes(1))
    _evidence(db_path, lead, "https://acme.example/new", "2026-10-30")

    text = _review(db_path, capsys)

    for title in ("Direct candidates", "Relationship prospects"):
        assert "Max evidence age: not configured" in _section(text, title)
    _, rows = _table(_section(text, "Direct candidates"))
    assert rows[0][10] == "31"


def test_same_day_evidence_prefers_the_highest_id(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path, answers=_yes(1))
    _evidence(db_path, lead, "https://acme.example/a", "2026-11-20")
    _evidence(db_path, lead, "https://acme.example/b", "2026-11-20")
    _, rows = _table(_section(_review(db_path, capsys), "Direct candidates"))
    assert rows[0][9:11] == ["https://acme.example/b", "10"]


def test_no_evidence_shows_dashes(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _lead(db_path, answers=_yes(1))
    _, rows = _table(_section(_review(db_path, capsys), "Direct candidates"))
    assert rows[0][9:11] == ["—", "—"]


# --- AC 5: legend, empty queues, --out ----------------------------------------------------


def test_legend_and_empty_queues(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = _review(db_path, capsys)

    direct = _section(text, "Direct candidates")
    partner = _section(text, "Relationship prospects")
    assert "- direct_signal: Current, directly sourced signal" in direct
    assert "- decision_maker: Decision maker identified" in direct
    assert "- fit: Fits the service area" in direct
    assert "- shared_clients: Serves the same clients" in partner
    assert "No direct candidates." in direct
    assert "No relationship prospects." in partner


def test_relationship_queue_uses_its_own_items(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path, "relationship_prospect", answers={"shared_clients": "yes"})
    header, rows = _table(_section(_review(db_path, capsys), "Relationship prospects"))
    assert header[5] == "shared_clients"
    assert header[6] == "Yes"
    assert rows[0][:7] == [str(lead), "—", "—", "none", "—", "yes", "1"]


def test_out_file_equals_the_printed_review(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = _lead(db_path, answers=_yes(2), founder_time=0.5, organization="Acme | Sons")
    _evidence(db_path, lead, "https://acme.example/new", "2026-10-30")
    printed = _review(db_path, capsys)
    out = tmp_path / "out" / "review.md"

    _review(db_path, capsys, "--out", str(out))

    assert out.read_text(encoding="utf-8") == printed
    assert "Acme \\| Sons" in printed


def test_explicit_missing_config_is_refused(
    db_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    missing = tmp_path / "nope.yaml"
    assert main(["review", "--config", str(missing), "--db", str(db_path)]) == 1
    assert capsys.readouterr().err.startswith("error:")


# --- reach: which contact routes a researched lead has ------------------------------------


@pytest.mark.parametrize(
    ("email", "phone", "address", "deleted", "expected"),
    [
        ("pat@acme.example", "+18015550100", "1 Main St, Sandy, UT", None, "email, phone, address"),
        (None, "+18015550100", None, None, "phone"),
        (None, None, "1 Main St, Sandy, UT", None, "address"),
        ("pat@acme.example", None, None, "2026-10-01T00:00:00Z", "none"),
    ],
)
def test_reach_lists_the_routes_on_file(
    db_path: Path,
    capsys: pytest.CaptureFixture[str],
    email: str | None,
    phone: str | None,
    address: str | None,
    deleted: str | None,
    expected: str,
) -> None:
    lead = _lead(db_path, answers=_yes(1), contact="Pat Lee")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE contacts SET email = ?, email_norm = ?, phone_e164 = ?, address = ?,"
            " deleted_at = ? WHERE id = (SELECT contact_id FROM leads WHERE id = ?)",
            (email, email, phone, address, deleted, lead),
        )
        conn.commit()
    finally:
        conn.close()

    _, rows = _table(_section(_review(db_path, capsys), "Direct candidates"))

    assert rows[0][3] == expected
