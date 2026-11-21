# sir-target: tests/test_no_hardcoded_schema_version.py
"""Tests derive the latest schema version instead of spelling it out (F-maintainability-7)."""

from __future__ import annotations

import re
from pathlib import Path

from cottonwood import db

LATEST_VERSION = len(db.discover_migrations())
TESTS = Path(__file__).resolve().parent

# Assertions about the schema version that name the newest number as a literal.
_PATTERNS = [
    rf"at version {LATEST_VERSION}\b",
    rf"user_version\)?\S*\s*==\s*{LATEST_VERSION}\b",
    rf"user_version\"\)\.fetchone\(\)\[0\]\s*==\s*{LATEST_VERSION}\b",
    rf"_version\([^)]*\)\s*==\s*{LATEST_VERSION}\b",
    rf"to_version\)\s*==\s*\([^)]*\b{LATEST_VERSION}\)",
    rf"==\s*\({LATEST_VERSION},\s*\[",
]


def test_latest_version_is_the_number_of_migrations() -> None:
    migrations = db.discover_migrations()
    assert LATEST_VERSION == migrations[-1].number == len(migrations)


def test_no_test_hard_codes_the_latest_version() -> None:
    hits = []
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(re.search(p, line) for p in _PATTERNS):
                hits.append(f"{path.name}:{number}: {line.strip()}")
    assert hits == []
