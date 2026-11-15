# sir-target: tests/test_review_order.py
"""Tests for review ordering: newest received first, not newest logged; missing time last."""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import db, review, timeutil
from cottonwood.cli import EXIT_OK, main

FIXED_NOW = "2026-11-18T17:00:00Z"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: FIXED_NOW)


def _log(db_path: Path, received: str, name: str) -> None:
    code = main(
        [
            "log-inbound",
            "--db",
            str(db_path),
            "--channel",
            "phone",
            "--received",
            received,
            "--segment",
            "commercial",
            "--name",
            name,
            "--confirm-duplicate",
        ]
    )
    assert code == EXIT_OK


def _insert_without_received(db_path: Path) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO leads (type, stage, segment, channel, received_at)"
            " VALUES ('inbound_inquiry', 'candidate', 'commercial', 'form', NULL)"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_out_of_order(db_path: Path) -> None:
    # Relayed inquiries arrive out of order: the logged order (id) differs from received order.
    _log(db_path, "2026-11-17 14:05", "Middle")  # id 1
    _log(db_path, "2026-11-16 09:30", "Oldest")  # id 2
    _log(db_path, "2026-11-18 08:15", "Newest")  # id 3
    _insert_without_received(db_path)  # id 4, highest id but no received time


def _table_rows(text: str) -> list[list[str]]:
    rows = [line for line in text.splitlines() if line.startswith("| ") and "---" not in line]
    return [[cell.strip() for cell in row.strip("|").split(" | ")] for row in rows[1:]]


def test_inbound_rows_follow_received_time_with_missing_time_last(db_path: Path) -> None:
    _seed_out_of_order(db_path)
    conn = db.connect(db_path)
    try:
        rows = review.inbound_rows(conn)
    finally:
        conn.close()
    assert [row["id"] for row in rows] == [3, 1, 2, 4]
    assert rows[-1]["received_at"] is None


def test_review_table_lists_newest_received_first_and_missing_time_last(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_out_of_order(db_path)
    capsys.readouterr()
    assert main(["review", "--db", str(db_path)]) == EXIT_OK
    rows = _table_rows(capsys.readouterr().out)
    assert [row[:2] for row in rows] == [
        ["3", "2026-11-18 08:15 -07:00"],
        ["1", "2026-11-17 14:05 -07:00"],
        ["2", "2026-11-16 09:30 -07:00"],
        ["4", "—"],
    ]
    assert [row[5] for row in rows] == ["Newest", "Middle", "Oldest", "—"]
