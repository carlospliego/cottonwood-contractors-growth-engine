"""Command-line entry point: argument parsing and one handler per command.

Exit codes: 0 = done, 1 = refused (a gate or validation failure), 2 = usage error.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from cottonwood import __version__, backup, config, db

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2

Handler = Callable[[argparse.Namespace], int]


@dataclass(frozen=True)
class Command:
    """One subcommand: its name, help line, argument setup and handler."""

    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    handler: Handler


def _add_migrate_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the migrate command's arguments."""
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )


def _run_migrate(args: argparse.Namespace) -> int:
    """Create or upgrade the database file to the newest migration."""
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        result = db.migrate(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"database {db_path} at version {result.to_version} (applied {len(result.applied)})")
    return EXIT_OK


def _add_backup_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the backup command's arguments."""
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--to",
        type=Path,
        default=None,
        help="backup folder (default: paths.backup_dir from the config file)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            f"config file, read only without --to"
            f" (default: ${config.CONFIG_ENV_VAR}, else {config.DEFAULT_CONFIG_PATH})"
        ),
    )


def _run_backup(args: argparse.Namespace) -> int:
    """Copy the database into the backup folder under a timestamped name."""
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        dest_dir: Path = (
            args.to if args.to is not None else config.load_config(args.config).backup_dir
        )
        written = backup.backup(db_path, dest_dir)
    except (backup.BackupError, config.ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"backup written: {written}")
    return EXIT_OK


# Subcommands register here; build_parser() adds each one in order.
COMMANDS: list[Command] = [
    Command(
        "migrate",
        "Create or upgrade the SQLite database by applying pending migrations.",
        _add_migrate_arguments,
        _run_migrate,
    ),
    Command(
        "backup",
        "Copy the database into the backup folder under a timestamped name.",
        _add_backup_arguments,
        _run_backup,
    ),
]


def build_parser(commands: Sequence[Command] | None = None) -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per command."""
    parser = argparse.ArgumentParser(
        prog="cottonwood",
        description="Cottonwood Contractors growth engine.",
    )
    parser.add_argument("--version", action="version", version=f"cottonwood {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for command in COMMANDS if commands is None else commands:
        sub = subparsers.add_parser(command.name, help=command.help, description=command.help)
        command.add_arguments(sub)
        sub.set_defaults(handler=command.handler)
    return parser


def _exit_code(code: str | int | None) -> int:
    """Turn a SystemExit code into an int exit code."""
    if code is None:
        return EXIT_OK
    if isinstance(code, int):
        return code
    print(code, file=sys.stderr)
    return EXIT_REFUSED


def main(argv: Sequence[str] | None = None, commands: Sequence[Command] | None = None) -> int:
    """Parse ``argv`` and run the chosen command. Returns the exit code."""
    parser = build_parser(commands)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc.code)
    handler: Handler = args.handler
    return handler(args)


def entry() -> None:
    """Console-script entry point."""
    sys.exit(main())
