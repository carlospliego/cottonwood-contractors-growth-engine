"""Tests for review: inquiries listed, tests labeled and excluded from counts (R-3, R-31)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config, db, review, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

FIXED_NOW = "2026-11-18T17:00:00Z"


@pytest.fixture(autouse=True)
def pinned_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # An absolute config path, so a test that changes directory reads the same checklists.
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: FIXED_NOW)


def _log(db_path: Path, channel: str, received: str, *args: str) -> None:
    code = main(
        [
            "log-inbound",
            "--db",
            str(db_path),
            "--channel",
            channel,
            "--received",
            received,
            "--confirm-duplicate",
            *args,
        ]
    )
    assert code == EXIT_OK


def _review(db_path: Path, capsys: pytest.CaptureFixture[str], *args: str) -> str:
    capsys.readouterr()
    assert main(["review", "--db", str(db_path), *args]) == EXIT_OK
    return capsys.readouterr().out


def _table_rows(text: str) -> list[list[str]]:
    rows = [line for line in text.splitlines() if line.startswith("| ") and "---" not in line]
    return [[cell.strip() for cell in row.strip("|").split(" | ")] for row in rows[1:]]


def test_rows_newest_first_with_local_time_and_supplied_fields(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _log(
        db_path,
        "form",
        "2026-11-16 09:30",
        "--segment",
        "commercial",
        "--name",
        "Pat Lee",
        "--email",
        "pat@example.com",
    )
    _log(
        db_path,
        "phone",
        "2026-11-17 14:05",
        "--segment",
        "residential",
        "--phone",
        "(801) 555-0134",
    )
    text = _review(db_path, capsys)

    assert "## Inbound inquiries" in text
    rows = _table_rows(text)
    assert len(rows) == 2
    newest, oldest = rows
    assert newest[:5] == ["2", "2026-11-17 14:05 -07:00", "phone", "residential", "candidate"]
    assert newest[5:8] == ["—", "—", "+18015550134"]
    assert oldest[:8] == [
        "1",
        "2026-11-16 09:30 -07:00",
        "form",
        "commercial",
        "candidate",
        "Pat Lee",
        "pat@example.com",
        "—",
    ]
    assert oldest[8:12] == ["—", "—", "—", "—"]


def test_test_inquiries_are_labeled(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _log(db_path, "form", "2026-11-16 09:30", "--segment", "commercial", "--name", "Real")
    _log(db_path, "form", "2026-11-16 10:30", "--segment", "commercial", "--name", "T", "--test")
    rows = _table_rows(_review(db_path, capsys))
    labels = {row[5]: row[-1] for row in rows}
    assert labels == {"T": "TEST", "Real": ""}


def test_counts_exclude_tests(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _log(db_path, "form", "2026-11-16 09:30", "--segment", "residential", "--name", "A", "--test")
    _log(db_path, "phone", "2026-11-16 09:45", "--segment", "commercial", "--name", "B", "--test")
    _log(db_path, "form", "2026-11-16 10:00", "--segment", "commercial", "--name", "C")
    text = _review(db_path, capsys)
    assert (
        "Inquiries: 1 (form 1, phone 0; commercial 1, residential 0, unknown 0)."
        " Test inquiries excluded: 2."
    ) in text


EMPTY_REVIEW = """\
# Review

Generated: 2026-11-18 10:00 -07:00

## Inbound inquiries

Inquiries: 0 (form 0, phone 0; commercial 0, residential 0, unknown 0). Test inquiries excluded: 0.

No inbound inquiries logged.

## Direct candidates

Order: most yes answers first; ties: lower founder time first (unknown last); then lowest lead id.
Max evidence age: not configured

No direct candidates.

## Relationship prospects

Order: most yes answers first; ties: lower founder time first (unknown last); then lowest lead id.
Max evidence age: not configured

No relationship prospects.
"""


def test_empty_database_prints_the_whole_empty_review(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The pinned clock (17:00Z) is shown in Denver time on the Generated line.
    assert _review(db_path, capsys) == EMPTY_REVIEW


def test_generated_line_follows_the_clock(
    db_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: "2026-07-04T06:30:00Z")
    assert "\nGenerated: 2026-07-04 00:30 -06:00\n" in _review(db_path, capsys)


def test_backslash_in_a_cell_is_escaped(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _log(
        db_path,
        "form",
        "2026-11-16 09:30",
        "--segment",
        "commercial",
        "--name",
        "P",
        "--company",
        "A\\B | C",
    )
    text = _review(db_path, capsys)
    assert "| A\\\\B \\| C |" in text


def test_out_writes_the_same_markdown_and_creates_folders(
    db_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _log(
        db_path,
        "form",
        "2026-11-16 09:30",
        "--segment",
        "commercial",
        "--name",
        "Pat",
        "--company",
        "Acme | Sons",
        "--scope",
        "lobby\nrefresh",
        "--budget",
        "25000",
    )
    printed = _review(db_path, capsys)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    out = _review(db_path, capsys, "--out", "out/review.md")

    written = work / "out" / "review.md"
    assert written.read_text(encoding="utf-8") == printed
    assert "out/review.md" in out
    assert "Acme \\| Sons" in printed
    assert "lobby refresh" in printed
    assert "25000" in printed


def test_missing_database_exits_1_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code = main(["review", "--db", str(tmp_path / "missing.db"), "--out", "out/review.md"])
    assert code == EXIT_REFUSED
    assert "error" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "missing.db").exists()


def test_deleted_contact_still_listed_with_cleared_fields(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _log(
        db_path,
        "form",
        "2026-11-16 09:30",
        "--segment",
        "commercial",
        "--name",
        "Pat",
        "--email",
        "pat@example.com",
        "--phone",
        "8015550134",
    )
    conn = db.connect(db_path)
    try:
        conn.execute(
            "UPDATE contacts SET name = NULL, email = NULL, email_norm = NULL,"
            " phone_e164 = NULL, deleted_at = ?",
            (FIXED_NOW,),
        )
        conn.commit()
    finally:
        conn.close()
    rows = _table_rows(_review(db_path, capsys))
    assert len(rows) == 1
    assert rows[0][0] == "1"
    assert rows[0][5:8] == ["—", "—", "—"]


def test_counted_leads_filter_selects_only_non_test_leads(db_path: Path) -> None:
    _log(db_path, "form", "2026-11-16 09:30", "--segment", "commercial", "--name", "Real")
    _log(db_path, "form", "2026-11-16 10:30", "--segment", "commercial", "--name", "T", "--test")
    conn = db.connect(db_path)
    try:
        counted = conn.execute(
            f"SELECT leads.id FROM leads WHERE {review.COUNTED_LEADS_FILTER}"
        ).fetchall()
        tests = conn.execute("SELECT id FROM leads WHERE is_test = 1").fetchall()
    finally:
        conn.close()
    assert [row[0] for row in counted] == [1]
    assert [row[0] for row in tests] == [2]


def test_counted_leads_filter_is_the_non_test_condition() -> None:
    assert review.COUNTED_LEADS_FILTER == "leads.is_test = 0"
