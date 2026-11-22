# sir-target: tests/test_procurement_url_host.py
"""An R-16 procurement URL must name a host, not just a netloc (F-correctness-7)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cottonwood import db, events, timeutil
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeutil, "utc_now", lambda: NOW)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    args = ["--channel", "phone", "--received", "2026-11-15 08:00", "--segment", "commercial"]
    assert main(["log-inbound", "--db", str(path), *args, "--name", "Pat Lee"]) == EXIT_OK
    return path


def _state(db_path: Path) -> tuple[int, str]:
    conn = sqlite3.connect(db_path)
    try:
        count = int(conn.execute("SELECT count(*) FROM activities").fetchone()[0])
        stage = str(conn.execute("SELECT stage FROM leads WHERE id = 1").fetchone()[0])
    finally:
        conn.close()
    return count, stage


def _qualify(db_path: Path, url: str) -> int:
    return main(
        [
            "log-event",
            "--db",
            str(db_path),
            "1",
            "remote_screen",
            "--at",
            "2026-11-16 09:30",
            "--stage",
            "buyer_need_confirmed",
            "--procurement-url",
            url,
        ]
    )


@pytest.mark.parametrize("url", ["http://:80", "https://:443/rfp", "http://user@", "http://@:8080"])
def test_url_without_a_host_exits_1_and_writes_nothing(
    db_path: Path, capsys: pytest.CaptureFixture[str], url: str
) -> None:
    before = _state(db_path)
    capsys.readouterr()

    assert _qualify(db_path, url) == EXIT_REFUSED

    err = capsys.readouterr().err
    assert err.startswith("error: procurement-url: must be an absolute http or https URL")
    assert _state(db_path) == before


@pytest.mark.parametrize(
    "url",
    ["https://bids.example.gov/rfp/123", "http://bids.example.gov:8080/x", "http://10.0.0.5/"],
)
def test_url_with_a_host_qualifies(db_path: Path, url: str) -> None:
    assert _qualify(db_path, url) == EXIT_OK
    assert _state(db_path)[1] == "buyer_need_confirmed"


@pytest.mark.parametrize(
    ("url", "ok"),
    [("http://:80", False), ("http://user@", False), ("https://example.com", True)],
)
def test_is_http_url_checks_the_host(url: str, ok: bool) -> None:
    assert events._is_http_url(url) is ok
