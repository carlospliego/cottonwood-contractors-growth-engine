"""Tests for the CLI skeleton: help, usage errors and the subcommand table."""

from __future__ import annotations

import argparse

import pytest

from cottonwood.cli import EXIT_OK, EXIT_USAGE, Command, main


def test_help_exits_zero_and_names_the_program(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--help"])
    assert isinstance(code, int)
    assert code == EXIT_OK
    assert "cottonwood" in capsys.readouterr().out


def test_no_subcommand_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])
    assert isinstance(code, int)
    assert code == EXIT_USAGE
    assert "usage: cottonwood" in capsys.readouterr().err


def test_unknown_subcommand_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["not-a-command"])
    assert code == EXIT_USAGE
    assert "invalid choice" in capsys.readouterr().err


def test_registered_command_runs_and_returns_its_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def add_arguments(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--name", required=True)

    def handler(args: argparse.Namespace) -> int:
        print(f"hello {args.name}")
        return 1

    commands = [Command("greet", "Say hello.", add_arguments, handler)]

    assert main(["greet", "--name", "test"], commands) == 1
    assert "hello test" in capsys.readouterr().out
    assert main(["--help"], commands) == EXIT_OK
    assert "greet" in capsys.readouterr().out
    assert main(["greet"], commands) == EXIT_USAGE
