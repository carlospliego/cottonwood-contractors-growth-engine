"""Command-line entry point: argument parsing and one handler per command.

Exit codes: 0 = done, 1 = refused (a gate or validation failure), 2 = usage error.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from cottonwood import __version__, backup, config, db, events, inbound, review, timeutil

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


def _add_log_inbound_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the log-inbound command's arguments: only what the inquirer supplied (R-1)."""
    parser.add_argument("--channel", required=True, choices=inbound.CHANNELS)
    parser.add_argument(
        "--received",
        required=True,
        metavar="WHEN",
        help="when it arrived: 'YYYY-MM-DD HH:MM' America/Denver, or UTC ending in Z",
    )
    parser.add_argument(
        "--segment",
        required=True,
        choices=inbound.SEGMENTS,
        help="as the inquirer stated it; unknown if they did not say",
    )
    parser.add_argument("--name", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument("--phone", default=None)
    parser.add_argument("--company", default=None, help="organization name, if given")
    parser.add_argument("--location", default=None, help="property location, if given")
    parser.add_argument("--scope", default=None, help="project scope, only if stated")
    parser.add_argument("--budget", default=None, help="stated budget as a decimal number")
    parser.add_argument(
        "--test", action="store_true", help="label a test submission (excluded from counts)"
    )
    parser.add_argument(
        "--confirm-duplicate",
        action="store_true",
        help="save even if it matches a same-day inquiry (otherwise asks, or refuses)",
    )
    parser.add_argument(
        "--actor",
        default=inbound.DEFAULT_ACTOR,
        help=f"who logs it (default: {inbound.DEFAULT_ACTOR})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )


def _duplicate_confirmed(
    args: argparse.Namespace, inquiry: inbound.Inquiry, duplicates: Sequence[int]
) -> bool:
    """Warn about same-day matches (R-2); True only on --confirm-duplicate or a typed yes."""
    ids = ", ".join(str(lead_id) for lead_id in duplicates)
    day = timeutil.local_date(inquiry.received_at).isoformat()
    print(f"warning: possible duplicate of lead(s) {ids} received {day}", file=sys.stderr)
    if args.confirm_duplicate:
        return True
    # A prompt would hang a script, so without a terminal the answer is no.
    if not sys.stdin.isatty():
        return False
    try:
        answer = input("Save anyway? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() in ("y", "yes")


def _run_log_inbound(args: argparse.Namespace) -> int:
    """Record a website-form or phone inquiry as an inbound_inquiry lead."""
    raw = inbound.RawInquiry(
        channel=args.channel,
        received=args.received,
        segment=args.segment,
        name=args.name,
        email=args.email,
        phone=args.phone,
        company=args.company,
        location=args.location,
        scope=args.scope,
        budget=args.budget,
        is_test=args.test,
        actor=args.actor,
    )
    try:
        inquiry = inbound.validate(raw)
    except inbound.InquiryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        conn = db.connect(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        duplicates = inbound.find_same_day_duplicates(
            conn, inquiry.email_norm, inquiry.phone_e164, inquiry.received_at
        )
        if duplicates and not _duplicate_confirmed(args, inquiry, duplicates):
            print("refused: duplicate not confirmed (use --confirm-duplicate)", file=sys.stderr)
            return EXIT_REFUSED
        lead_id = inbound.log_inquiry(conn, inquiry, duplicate_of=duplicates)
    except sqlite3.Error as exc:
        print(f"error: could not save the inquiry: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    label = " TEST" if inquiry.is_test else ""
    print(
        f"logged inquiry lead {lead_id} ({inquiry.channel}, {inquiry.segment},"
        f" received {timeutil.display_local(inquiry.received_at)}){label}"
    )
    return EXIT_OK


def _add_review_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the review command's arguments."""
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the Markdown to this file (e.g. out/review.md; out/ is git-ignored)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )


def _run_review(args: argparse.Namespace) -> int:
    """Print the review, or write it to --out for sending to the founder (R-31)."""
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        conn = db.connect(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        text = review.render_review(conn, timeutil.utc_now())
    except sqlite3.Error as exc:
        print(f"error: could not read the database: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    if args.out is None:
        sys.stdout.write(text)
        return EXIT_OK
    out_path: Path = args.out
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"error: could not write {out_path}: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"review written: {out_path}")
    return EXIT_OK


def _add_log_event_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the log-event command's arguments (R-15)."""
    parser.add_argument("lead_id", type=int, metavar="LEAD_ID", help="the lead's id")
    parser.add_argument(
        "type", choices=events.EVENT_TYPES, metavar="TYPE", help=", ".join(events.EVENT_TYPES)
    )
    parser.add_argument(
        "--at",
        required=True,
        metavar="WHEN",
        help="when it happened: 'YYYY-MM-DD HH:MM' America/Denver, or UTC ending in Z",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="what happened (required for note); never put contact details here",
    )
    parser.add_argument(
        "--stage",
        default=None,
        help="move the lead to this R-14 stage (the move is recorded as a stage_change)",
    )
    parser.add_argument(
        "--need",
        default=None,
        help=f"the prospect's confirmed need; only with --stage {events.QUALIFIED_STAGE}",
    )
    parser.add_argument(
        "--procurement-url",
        default=None,
        help=f"URL of an accessible active procurement; only with --stage {events.QUALIFIED_STAGE}",
    )
    parser.add_argument(
        "--actor",
        default=events.DEFAULT_ACTOR,
        help=f"who logs it (default: {events.DEFAULT_ACTOR})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )


def _run_log_event(args: argparse.Namespace) -> int:
    """Record an event on a lead as one activity."""
    raw = events.RawEvent(
        lead_id=args.lead_id,
        type=args.type,
        at=args.at,
        note=args.note,
        actor=args.actor,
        stage=args.stage,
        need=args.need,
        procurement_url=args.procurement_url,
    )
    try:
        event = events.validate_event(raw, timeutil.utc_now())
    except events.EventError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        conn = db.connect(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        logged = events.log_event(conn, event)
    except events.EventError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except sqlite3.Error as exc:
        print(f"error: could not save the event: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    line = (
        f"logged {event.type} activity {logged.event_id} for lead {event.lead_id}"
        f" at {timeutil.display_local(event.occurred_at)}"
    )
    if logged.stage_change_id is not None:
        line += f"; stage {logged.from_stage} -> {event.stage}"
    print(line)
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
    Command(
        "log-inbound",
        "Record a website-form or phone inquiry as an inbound lead.",
        _add_log_inbound_arguments,
        _run_log_inbound,
    ),
    Command(
        "review",
        "Print or write the Markdown review of inbound inquiries for the founder.",
        _add_review_arguments,
        _run_review,
    ),
    Command(
        "log-event",
        "Record an event on a lead (acknowledgement, call, walkthrough, ...).",
        _add_log_event_arguments,
        _run_log_event,
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
