# sir-target: tests/test_report_inbound_other.py
"""The inbound report counts an unknown channel or segment under 'other' (CCGE-156).

leads.channel and leads.segment have no CHECK constraint, so a value written by SQL or a
restore (channel 'fax', segment 'industrial') was counted in the total but under no channel
or segment, and the lines no longer added up to the total.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cottonwood import config, db, report, timeutil
from cottonwood.cli import EXIT_OK, main

NOW = "2026-12-01T00:00:00Z"  # Denver today 2026-11-30; --period 30d is 2026-11-01..11-30


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture(autouse=True)
def pilot_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "pilot.yaml"
    path.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _inquiry(db_path: Path, channel: str, segment: str) -> None:
    args = ["log-inbound", "--db", str(db_path), "--channel", channel]
    args += ["--received", "2026-11-20 09:00", "--segment", segment]
    args += ["--name", "Pat Lee", "--confirm-duplicate"]
    assert main(args) == EXIT_OK


def _insert_raw(db_path: Path, channel: str, segment: str) -> None:
    """INSERT an inbound lead directly in SQL, as a restore could, copying the newest one."""
    columns = (
        "type, organization_id, contact_id, stage, property_location, hypothesis, next_action,"
        " founder_time_h, value_amount, value_basis, referred_by, is_test, received_at,"
        " project_scope, verified_facts, checklist"
    )
    conn = db.connect(db_path)
    try:
        conn.execute(
            f"INSERT INTO leads (channel, segment, {columns})"
            f" SELECT ?, ?, {columns} FROM leads WHERE id = (SELECT max(id) FROM leads)",
            (channel, segment),
        )
        conn.commit()
        row = conn.execute(
            "SELECT channel, segment FROM leads WHERE id = (SELECT max(id) FROM leads)"
        ).fetchone()
        assert tuple(row) == (channel, segment)
    finally:
        conn.close()


def _report(db_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    capsys.readouterr()
    assert main(["report", "--db", str(db_path), "--period", "30d"]) == EXIT_OK
    return capsys.readouterr().out


def _counts(text: str, label: str) -> dict[str, int]:
    prefix = f"- {label} "
    found = {}
    for line in text.splitlines():
        if line.startswith(prefix):
            name, value = line[len(prefix) :].split(": ")
            found[name] = int(value)
    return found


def _total(text: str) -> int:
    (line,) = [x for x in text.splitlines() if x.startswith(f"- {report.LABEL_INQUIRIES}: ")]
    return int(line.split(": ")[1])


def test_unknown_channel_and_segment_are_counted_under_other(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _inquiry(db_path, "form", "commercial")
    _inquiry(db_path, "phone", "residential")
    _insert_raw(db_path, "fax", "industrial")
    text = _report(db_path, capsys)
    channels = _counts(text, report.LABEL_CHANNEL)
    segments = _counts(text, report.LABEL_SEGMENT)
    assert _total(text) == 3
    assert sum(channels.values()) == 3
    assert sum(segments.values()) == 3
    assert channels == {"form": 1, "phone": 1, report.OTHER: 1}
    assert segments == {"commercial": 1, "residential": 1, "unknown": 0, report.OTHER: 1}
    # The known lines keep their order; 'other' comes after them.
    assert list(channels) == ["form", "phone", report.OTHER]
    assert list(segments) == ["commercial", "residential", "unknown", report.OTHER]


def test_no_other_line_when_every_value_is_known(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _inquiry(db_path, "form", "commercial")
    _inquiry(db_path, "phone", "unknown")
    text = _report(db_path, capsys)
    assert f"{report.LABEL_CHANNEL} {report.OTHER}" not in text
    assert f"{report.LABEL_SEGMENT} {report.OTHER}" not in text
    assert sum(_counts(text, report.LABEL_CHANNEL).values()) == _total(text) == 2
    assert sum(_counts(text, report.LABEL_SEGMENT).values()) == 2
