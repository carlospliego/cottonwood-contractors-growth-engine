# sir-target: tests/test_duplicate_prompt_stderr.py
"""The duplicate prompt goes to stderr, so it shows when stdout is redirected (F-correctness)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from cottonwood import db
from cottonwood.cli import DUPLICATE_PROMPT, EXIT_OK, EXIT_REFUSED, main

ARGS = (
    "--channel",
    "form",
    "--received",
    "2026-11-16 09:30",
    "--segment",
    "commercial",
    "--name",
    "Pat Lee",
    "--email",
    "pat@example.com",
)


class _TtyStdin(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def db_with_lead(tmp_path: Path) -> Path:
    path = tmp_path / "cottonwood.db"
    db.migrate(path)
    assert main(["log-inbound", "--db", str(path), *ARGS]) == EXIT_OK
    return path


@pytest.mark.parametrize(("answer", "code"), [("y", EXIT_OK), ("n", EXIT_REFUSED)])
def test_prompt_is_on_stderr_not_stdout(
    db_with_lead: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    answer: str,
    code: int,
) -> None:
    capsys.readouterr()
    monkeypatch.setattr(sys, "stdin", _TtyStdin(answer + "\n"))

    assert main(["log-inbound", "--db", str(db_with_lead), *ARGS]) == code

    out, err = capsys.readouterr()
    assert DUPLICATE_PROMPT in err
    assert DUPLICATE_PROMPT not in out
    assert err.index("warning: possible duplicate") < err.index(DUPLICATE_PROMPT)


def test_input_builtin_is_not_used(db_with_lead: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(prompt: object = "") -> str:
        raise AssertionError("input() writes its prompt to stdout")

    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr(sys, "stdin", _TtyStdin("y\n"))
    assert main(["log-inbound", "--db", str(db_with_lead), *ARGS]) == EXIT_OK
