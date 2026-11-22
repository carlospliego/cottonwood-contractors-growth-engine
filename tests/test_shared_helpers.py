# sir-target: tests/test_shared_helpers.py
"""_clean and _rowid are defined once and imported where used (F-maintainability-9)."""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

import cottonwood
from cottonwood import _shared, events, inbound, prospects

PACKAGE = Path(cottonwood.__file__).parent


def _definitions(name: str) -> list[str]:
    found = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
                found.append(path.relative_to(PACKAGE).as_posix())
    return found


@pytest.mark.parametrize("name", ["_clean", "_rowid"])
def test_each_helper_is_defined_once(name: str) -> None:
    assert _definitions(name) == ["_shared.py"]


def test_the_modules_use_the_shared_helpers() -> None:
    # vars(): the modules import these names, they do not re-export them.
    for module in (events, inbound):
        assert vars(module)["_clean"] is _shared._clean
    for module in (events, inbound, prospects):
        assert vars(module)["_rowid"] is _shared._rowid


def test_the_helpers_behave_as_before() -> None:
    assert _shared._clean(None) is None
    assert _shared._clean("   ") is None
    assert _shared._clean("  Pat Lee ") == "Pat Lee"
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        assert _shared._rowid(conn.execute("INSERT INTO t (v) VALUES ('a')")) == 1
    finally:
        conn.close()
