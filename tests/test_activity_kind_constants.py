# sir-target: tests/test_activity_kind_constants.py
"""events.py names the correction and stage_change activity types (F-maintainability-6)."""

from __future__ import annotations

import ast
from pathlib import Path

from cottonwood import events

SOURCE = Path(events.__file__)
NAMES = {"correction": "CORRECTION_KIND", "stage_change": "STAGE_CHANGE_KIND"}


def test_the_constants_hold_the_stored_type_names() -> None:
    assert events.CORRECTION_KIND == "correction"
    assert events.STAGE_CHANGE_KIND == "stage_change"


def _bare_type_strings(tree: ast.AST) -> list[tuple[int, str]]:
    """Every string constant, or SQL text piece, that is a bare type name or quotes one."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for name in NAMES:
                if node.value == name or f"'{name}'" in node.value:
                    found.append((node.lineno, node.value))
    return found


def test_only_the_definitions_spell_the_type_names() -> None:
    tree = ast.parse(SOURCE.read_text())
    definitions = {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in NAMES.values()
    }
    assert len(definitions) == 2
    stray = [(line, text) for line, text in _bare_type_strings(tree) if line not in definitions]
    assert stray == []


def test_the_sql_is_built_from_the_constants() -> None:
    assert f"r.type = '{events.CORRECTION_KIND}'" in events._IS_REVERT_SQL
    assert events.COUNTED_ACTIVITIES_SQL.startswith(f"a.type <> '{events.CORRECTION_KIND}'")
    assert f"a.type = '{events.STAGE_CHANGE_KIND}'" in events.COUNTED_ACTIVITIES_SQL
    assert events._EFFECTIVE_STAGE_CHANGE_SQL.startswith(
        f"a.type = '{events.STAGE_CHANGE_KIND}' AND NOT EXISTS"
    )
    assert events._voiding_sql("x") == (
        f"c.type = '{events.CORRECTION_KIND}' AND c.voids_activity_id = x"
    )
