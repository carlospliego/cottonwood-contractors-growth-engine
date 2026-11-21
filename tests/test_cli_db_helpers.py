# sir-target: tests/test_cli_db_helpers.py
"""Every database command gets --db from one helper and resolves it one way (F-maint-6)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from cottonwood import cli, db

CLI_SRC = Path(cli.__file__).read_text(encoding="utf-8")


def _subparsers() -> dict[str, argparse.ArgumentParser]:
    parser = cli.build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    raise AssertionError("no subcommands")


def _db_option(sub: argparse.ArgumentParser) -> argparse.Action | None:
    return next((a for a in sub._actions if "--db" in a.option_strings), None)


def test_the_option_is_defined_once_in_the_source() -> None:
    assert CLI_SRC.count('"--db"') == 1
    assert "args.db if args.db is not None" not in CLI_SRC
    assert CLI_SRC.count("_add_db_argument(parser)") >= 17
    assert CLI_SRC.count("_db_path(args)") >= 19


def test_every_db_command_has_the_same_option() -> None:
    with_db = {name: opt for name, sub in _subparsers().items() if (opt := _db_option(sub))}
    assert len(with_db) >= 17
    for name, opt in with_db.items():
        assert opt.default is None, name
        assert opt.type is Path, name
        assert db.DB_ENV_VAR in (opt.help or ""), name


def test_db_path_prefers_the_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(db.DB_ENV_VAR, str(tmp_path / "env.db"))
    assert cli._db_path(argparse.Namespace(db=tmp_path / "flag.db")) == tmp_path / "flag.db"


def test_db_path_falls_back_to_the_env_then_the_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(db.DB_ENV_VAR, str(tmp_path / "env.db"))
    assert cli._db_path(argparse.Namespace(db=None)) == tmp_path / "env.db"
    monkeypatch.delenv(db.DB_ENV_VAR)
    assert cli._db_path(argparse.Namespace(db=None)) == db.DEFAULT_DB_PATH


def test_a_command_uses_the_flag_end_to_end(tmp_path: Path) -> None:
    path = tmp_path / "chosen.db"
    assert cli.main(["migrate", "--db", str(path)]) == cli.EXIT_OK
    assert path.exists()
