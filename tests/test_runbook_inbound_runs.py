# sir-target: tests/test_runbook_inbound_runs.py
"""The runbook's inbound commands and SQL, run as written (F-testing-9).

tests/test_runbook_inbound.py checks the runbook's wording. This file extracts the indented
`uv run cottonwood ...` commands and the SQL block, runs them against a temp database through
main() and sqlite3, and checks the outcome the runbook describes.
"""

from __future__ import annotations

import re
import shlex
import sqlite3
import sys
from pathlib import Path

import pytest

from cottonwood import config, db, eligibility
from cottonwood.cli import EXIT_OK, EXIT_REFUSED, main

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = REPO_ROOT / "docs" / "runbook.md"
PREFIX = ["uv", "run", "cottonwood"]


def _section(title: str) -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"runbook has no '## {title}' section"
    return match.group(1)


def _commands(title: str) -> list[list[str]]:
    """The section's indented `uv run cottonwood` command lines, as argument lists."""
    lines = [line[4:] for line in _section(title).splitlines() if line.startswith("    uv run ")]
    commands = [shlex.split(line) for line in lines]
    assert all(command[:3] == PREFIX for command in commands)
    return [command[3:] for command in commands]


def _sql_block(title: str) -> str:
    blocks = re.findall(r"```sql\n(.*?)```", _section(title), re.S)
    assert len(blocks) == 1, f"expected one sql block in '## {title}'"
    return str(blocks[0])


def _run(command: list[str], db_path: Path) -> int:
    """Run a runbook command against the temp database: --db goes after the subcommand."""
    return main([command[0], "--db", str(db_path), *command[1:]])


class _NonTtyStdin:
    def isatty(self) -> bool:
        return False

    def readline(self) -> str:
        raise AssertionError("no prompt is expected outside a terminal")


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pilot = tmp_path / "pilot.yaml"
    pilot.write_text("paths:\n  backup_dir: data/backups\n", encoding="utf-8")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(pilot))
    monkeypatch.setattr(sys, "stdin", _NonTtyStdin())
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    return path


def _table_rows(text: str) -> list[list[str]]:
    section = text.split("## Inbound inquiries", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| ") and "---" not in line]
    return [[cell.strip() for cell in row.strip("|").split(" | ")] for row in rows[1:]]


def test_checklist_test_submissions_log_and_review_as_the_runbook_says(db_path: Path) -> None:
    commands = _commands("Inbound verification checklist")
    logs = [c for c in commands if c[0] == "log-inbound"]
    assert len(logs) == 2
    assert [_run(command, db_path) for command in logs] == [EXIT_OK, EXIT_OK]

    # "Then run `uv run cottonwood review --out out/review.md`" (inline in the prose).
    assert main(["review", "--db", str(db_path), "--out", "out/review.md"]) == EXIT_OK
    written = Path("out/review.md").read_text(encoding="utf-8")
    rows = _table_rows(written)
    assert len(rows) == 2
    assert all(row[-1] == "TEST" for row in rows)
    assert "Test inquiries excluded: 2" in written


def test_second_checklist_submission_needs_confirm_duplicate(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = (
        c for c in _commands("Inbound verification checklist") if c[0] == "log-inbound"
    )
    assert "--confirm-duplicate" in second
    assert _run(first, db_path) == EXIT_OK
    capsys.readouterr()

    without = [arg for arg in second if arg != "--confirm-duplicate"]
    assert _run(without, db_path) == EXIT_REFUSED
    assert "warning: possible duplicate of lead(s) 1 received 2026-11-16" in capsys.readouterr().err


def test_relay_examples_log_and_review_with_the_fields_given(db_path: Path) -> None:
    commands = [c for c in _commands("Relay") if c[0] == "log-inbound"]
    assert len(commands) == 2
    assert [_run(command, db_path) for command in commands] == [EXIT_OK, EXIT_OK]

    assert main(["review", "--db", str(db_path), "--out", "out/review.md"]) == EXIT_OK
    written = Path("out/review.md").read_text(encoding="utf-8")
    assert "Inquiries: 2 (form 1, phone 1; commercial 1, residential 0, unknown 1)." in written
    phone, form = _table_rows(written)
    assert form[2:4] == ["form", "commercial"]
    assert "Pat Lee" in form and "pat@example.com" in form
    assert "Acme Holdings" in form and "lobby refresh" in form
    assert phone[2:4] == ["phone", "unknown"]
    assert "+18015550134" in phone


def test_relay_form_example_logged_again_is_refused_as_a_duplicate(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    form = next(c for c in _commands("Relay") if c[0] == "log-inbound")
    assert _run(form, db_path) == EXIT_OK
    capsys.readouterr()
    assert _run(form, db_path) == EXIT_REFUSED
    assert "warning: possible duplicate of lead(s) 1 received 2026-11-16" in capsys.readouterr().err
    assert _run([*form, "--confirm-duplicate"], db_path) == EXIT_OK


def test_relay_opt_out_sql_suppresses_and_is_safe_to_repeat(db_path: Path) -> None:
    sql = _sql_block("Relay")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.executescript(sql)  # "an address already suppressed is kept as it is"
        rows = conn.execute("SELECT email_norm, reason, source FROM suppression").fetchall()
        assert rows == [("pat@example.com", "opt_out", "relay")]
        assert eligibility._is_suppressed(conn, "pat@example.com")
    finally:
        conn.close()
