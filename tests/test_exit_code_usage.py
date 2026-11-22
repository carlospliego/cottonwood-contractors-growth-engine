# sir-target: tests/test_exit_code_usage.py
"""Usage errors exit with EXIT_USAGE; _exit_code has no string branch (F-maintainability-1, -2)."""

from __future__ import annotations

import inspect

import pytest

from cottonwood import cli
from cottonwood.cli import EXIT_OK, EXIT_USAGE, main


def test_no_arguments_is_a_usage_error() -> None:
    assert EXIT_USAGE == 2
    assert main([]) == EXIT_USAGE


def test_an_unknown_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["no-such-command"]) == EXIT_USAGE
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize(("code", "expected"), [(None, EXIT_OK), (0, EXIT_OK), (2, EXIT_USAGE)])
def test_exit_code_maps_argparse_codes(code: int | None, expected: int) -> None:
    assert cli._exit_code(code) == expected


def test_exit_code_uses_exit_usage_and_never_refuses() -> None:
    source = inspect.getsource(cli._exit_code)
    assert "EXIT_USAGE" in source
    assert "EXIT_REFUSED" not in source
    assert "isinstance" not in source
