# sir-target: tests/test_log_reply_date_and_rollback.py
"""log-reply refuses a future or malformed --date, and a failed suppression rolls the reply back.

F-testing-6 (review 20261115-191126): no test gave log-reply a bad --date, and none made the
suppression insert fail after the reply insert, so a missing date check or a reply committed
without its suppression would pass.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from test_log_reply import (  # noqa: F401  (pytest fixtures)
    _activities,
    _run,
    _suppression,
    database,
    fixed_now,
)

from cottonwood import gate, timeutil
from cottonwood.cli import EXIT_REFUSED


def _snapshot(path: Path) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    return [tuple(row) for row in _activities(path)], [tuple(row) for row in _suppression(path)]


def test_utc_now_is_pinned() -> None:
    assert timeutil.utc_now() == "2026-12-01T00:00:00Z"


@pytest.mark.parametrize("value", ["2026-12-01", "30/11/2026"])
def test_a_future_or_malformed_date_is_refused_and_nothing_is_appended(
    database: Path,  # noqa: F811
    value: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = _snapshot(database)
    capsys.readouterr()
    assert _run(database, "log-reply", "1", "other", "--date", value) == EXIT_REFUSED
    assert capsys.readouterr().err.startswith("error: date:")
    assert _snapshot(database) == before


def test_a_failed_suppression_insert_stores_no_reply(
    database: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def failing_insert(*args: object, **kwargs: object) -> object:
        calls.append("called")
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(gate, "_insert_suppression", failing_insert)
    before = _snapshot(database)
    capsys.readouterr()
    assert _run(database, "log-reply", "1", "opt_out", "--date", "2026-11-30") == EXIT_REFUSED
    assert calls == ["called"]  # the reply insert ran first, then the suppression failed
    assert "disk I/O error" in capsys.readouterr().err
    assert _activities(database, "reply") == []
    assert _snapshot(database) == before
