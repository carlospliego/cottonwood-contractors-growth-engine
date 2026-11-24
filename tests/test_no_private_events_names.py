"""No module but events.py calls an underscored events name (CCGE-154).

CCGE-126 gave events public names for the helpers other modules use; hand_review and send
still called events._parse_entry_date, _voided_sql, _insert_activity, _day_start and
_is_http_url, so a change to one of those could break them unnoticed.
"""

from __future__ import annotations

import re
from pathlib import Path

import cottonwood
from cottonwood import events

PACKAGE = Path(cottonwood.__file__).resolve().parent
PRIVATE_USE = re.compile(r"\bevents\._[A-Za-z]")


def test_no_module_but_events_uses_an_underscored_events_name() -> None:
    offenders = [
        f"{path.relative_to(PACKAGE)}:{number}: {line.strip()}"
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.name != "events.py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if PRIVATE_USE.search(line)
    ]
    assert offenders == []


def test_the_scan_finds_a_private_use() -> None:
    assert PRIVATE_USE.search("day = events._parse_entry_date(text, today)")
    assert not PRIVATE_USE.search("day = events.parse_entry_date(text, today)")


def test_is_http_url_is_public_and_is_the_same_helper() -> None:
    assert events.is_http_url is events._is_http_url
    assert events.is_http_url("https://example.com/bid")
    assert not events.is_http_url("ftp://example.com/bid")
