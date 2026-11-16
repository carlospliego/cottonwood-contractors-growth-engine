# sir-target: tests/test_research_skill_scoping.py
"""Regression F-security-basics-1: the research-prospects skill must scope its file tools so
injected web text cannot read local PII or write outside out/research/."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

SKILL = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "research-prospects" / "SKILL.md"
ENTRY = re.compile(r"^(?P<name>[A-Za-z_][\w]*)(?:\((?P<spec>.*)\))?$")


def _tools() -> list[str]:
    text = SKILL.read_text(encoding="utf-8")
    end = text.index("\n---\n", 4)
    tools = yaml.safe_load(text[4:end])["allowed-tools"]
    if isinstance(tools, str):
        tools = [part.strip() for part in tools.split(",")]
    return list(tools)


def test_no_unscoped_or_forbidden_tools() -> None:
    tools = _tools()
    parsed = []
    for tool in tools:
        match = ENTRY.match(tool)
        assert match, tool
        parsed.append((match["name"], match["spec"]))
    names = {name for name, _ in parsed}
    assert not names & {"Glob", "Grep", "Bash", "Edit"}
    assert {"WebSearch", "WebFetch"} <= names
    for name, spec in parsed:
        if name in {"Read", "Write"}:
            assert spec, f"bare {name} is unscoped"


def test_write_is_confined_to_out_research() -> None:
    specs = [m["spec"] for m in map(ENTRY.match, _tools()) if m and m["name"] == "Write"]
    assert specs
    for spec in specs:
        assert spec.startswith("out/research/")
        assert ".." not in spec


def test_read_is_limited_to_config_and_schema() -> None:
    specs = {m["spec"] for m in map(ENTRY.match, _tools()) if m and m["name"] == "Read"}
    assert specs == {
        "config/pilot.yaml",
        "cottonwood/schemas/research-record.schema.json",
    }
