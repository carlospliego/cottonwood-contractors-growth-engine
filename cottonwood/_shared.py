"""Small helpers shared by the modules that validate input and write rows (F-maintainability-9).

Package-internal: events, inbound and prospects import these by name instead of each keeping a
verbatim copy.
"""

from __future__ import annotations

import sqlite3


def _clean(value: str | None) -> str | None:
    """Strip a text option; blank means not supplied."""
    if value is None:
        return None
    text = value.strip()
    return text or None


def _rowid(cursor: sqlite3.Cursor) -> int:
    """Return the id of the row an INSERT just wrote."""
    if cursor.lastrowid is None:
        raise sqlite3.DatabaseError("insert returned no row id")
    return cursor.lastrowid
