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

from cottonwood import (
    __version__,
    backup,
    config,
    db,
    eligibility,
    events,
    hand_review,
    inbound,
    prospects,
    report,
    review,
    timeutil,
    validate,
)

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
        "--config",
        type=Path,
        default=None,
        help=(
            f"config file with the review checklists (default: ${config.CONFIG_ENV_VAR}, else"
            f" {config.DEFAULT_CONFIG_PATH})"
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )


def _run_review(args: argparse.Namespace) -> int:
    """Print the review, or write it to --out for sending to the founder (R-13, R-31)."""
    try:
        review_config = _import_review_config(args.config)
    except config.ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        conn = db.connect(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        text = review.render_review(conn, timeutil.utc_now(), review_config)
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


def _add_report_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the report command's arguments."""
    parser.add_argument(
        "--period",
        choices=tuple(report.PERIODS),
        default=None,
        help="the last 7 or 30 America/Denver dates, ending today",
    )
    parser.add_argument(
        "--from",
        dest="from_",
        default=None,
        metavar="YYYY-MM-DD",
        help="first America/Denver date of the period (with --to)",
    )
    parser.add_argument(
        "--to",
        default=None,
        metavar="YYYY-MM-DD",
        help="last America/Denver date of the period, inclusive (with --from)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the Markdown to this file (e.g. out/report.md; out/ is git-ignored)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"config file (default: ${config.CONFIG_ENV_VAR}, else {config.DEFAULT_CONFIG_PATH})",
    )


def _run_report(args: argparse.Namespace) -> int:
    """Print the weekly report, or write it to --out for sending to the founder (R-28)."""
    try:
        period = report.parse_period(args.period, args.from_, args.to, events.denver_today())
        cfg = config.load_config(args.config)
    except (report.ReportError, config.ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        conn = db.connect(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        text = report.render_report(report.build_report(conn, period, cfg, timeutil.utc_now()))
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
    print(f"report written: {out_path}")
    return EXIT_OK


def _add_log_event_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the log-event command's arguments (R-15)."""
    parser.add_argument("lead_id", type=int, metavar="LEAD_ID", help="the lead's id")
    parser.add_argument(
        "type",
        choices=(*events.EVENT_TYPES, "correction"),
        metavar="TYPE",
        help=", ".join(events.EVENT_TYPES) + ", or correction (with --voids)",
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
        "--voids",
        type=int,
        default=None,
        metavar="ACTIVITY_ID",
        help="with correction: the event activity to void (R-17)",
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


def _run_correction(args: argparse.Namespace) -> int:
    """Void an earlier event of the lead with an appended correction (R-17)."""
    if args.voids is None:
        print("error: voids: a correction needs --voids ACTIVITY_ID", file=sys.stderr)
        return EXIT_REFUSED
    for flag, value in (
        ("stage", args.stage),
        ("need", args.need),
        ("procurement-url", args.procurement_url),
    ):
        if value is not None:
            print(f"error: {flag}: not allowed with a correction", file=sys.stderr)
            return EXIT_REFUSED
    raw = events.RawCorrection(
        lead_id=args.lead_id, voids_id=args.voids, at=args.at, note=args.note, actor=args.actor
    )
    try:
        correction = events.validate_correction(raw, timeutil.utc_now())
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
        logged = events.log_correction(conn, correction)
    except events.EventError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except sqlite3.Error as exc:
        print(f"error: could not save the correction: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    line = (
        f"logged correction activity {logged.correction_id} for lead {correction.lead_id}"
        f" at {timeutil.display_local(correction.occurred_at)}; voids activity"
        f" {correction.voids_id}"
    )
    if logged.stage_change_id is not None:
        line += f"; stage {logged.from_stage} -> {logged.to_stage}"
    print(line)
    return EXIT_OK


def _run_log_event(args: argparse.Namespace) -> int:
    """Record an event on a lead as one activity, or a correction voiding one."""
    if args.type == "correction":
        return _run_correction(args)
    if args.voids is not None:
        print("error: voids: only allowed with type correction", file=sys.stderr)
        return EXIT_REFUSED
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


def _add_entry_arguments(parser: argparse.ArgumentParser, *, amount: str, help_text: str) -> None:
    """Arguments shared by log-time and log-cost (R-30)."""
    parser.add_argument("amount", nargs="?", default=None, metavar=amount, help=help_text)
    parser.add_argument("--date", default=None, help="the day it happened, YYYY-MM-DD (Denver)")
    parser.add_argument("--category", default=None, help="what it was for (stored lowercase)")
    parser.add_argument(
        "--estimated",
        action="store_true",
        default=None,
        help="an estimate rather than an observed figure (R-29)",
    )
    parser.add_argument(
        "--note", default=None, help="optional detail; never put contact details here"
    )
    parser.add_argument(
        "--voids",
        type=int,
        default=None,
        metavar="ACTIVITY_ID",
        help="void this earlier entry instead of logging a new one (R-17)",
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


def _add_log_time_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the log-time command's arguments."""
    _add_entry_arguments(parser, amount="HOURS", help_text="hours spent, e.g. 1.5 (at most 24)")
    parser.add_argument(
        "--person",
        choices=events.PEOPLE,
        default=None,
        help=f"whose hours (default: {events.DEFAULT_PERSON})",
    )


def _add_log_cost_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the log-cost command's arguments."""
    _add_entry_arguments(parser, amount="AMOUNT", help_text="US dollars spent, e.g. 49.00")


def _void_entry_conflict(args: argparse.Namespace, amount_name: str) -> str | None:
    """With --voids, name the first entry option also given; without it, the first missing."""
    given = [
        (amount_name, args.amount),
        ("date", args.date),
        ("category", args.category),
    ]
    if args.voids is not None:
        extra = [*given, ("person", getattr(args, "person", None)), ("estimated", args.estimated)]
        for name, value in extra:
            if value is not None:
                return f"voids: not allowed with {name}"
        return None
    for name, value in given:
        if value is None:
            return f"{name}: required unless --voids is given"
    return None


def _run_entry(args: argparse.Namespace, kind: str, amount_name: str) -> int:
    """Validate, connect and write one time or cost entry, or void one."""
    problem = _void_entry_conflict(args, amount_name)
    if problem is not None:
        print(f"error: {problem}", file=sys.stderr)
        return EXIT_REFUSED
    entry: events.TimeEntry | events.CostEntry | None = None
    if args.voids is None:
        today = events.denver_today()
        try:
            if kind == events.TIME_KIND:
                entry = events.validate_time(
                    events.RawTime(
                        hours=args.amount,
                        date=args.date,
                        category=args.category,
                        person=args.person or events.DEFAULT_PERSON,
                        estimated=bool(args.estimated),
                        note=args.note,
                        actor=args.actor,
                    ),
                    today,
                )
            else:
                entry = events.validate_cost(
                    events.RawCost(
                        amount_usd=args.amount,
                        date=args.date,
                        category=args.category,
                        estimated=bool(args.estimated),
                        note=args.note,
                        actor=args.actor,
                    ),
                    today,
                )
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
        if isinstance(entry, events.TimeEntry):
            activity_id = events.log_time(conn, entry)
        elif isinstance(entry, events.CostEntry):
            activity_id = events.log_cost(conn, entry)
        else:
            activity_id = events.void_entry(
                conn, args.voids, kind, args.actor, timeutil.utc_now(), args.note
            )
    except events.EventError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except sqlite3.Error as exc:
        print(f"error: could not save the entry: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    if entry is None:
        print(f"logged correction activity {activity_id}; voids {kind} activity {args.voids}")
    elif isinstance(entry, events.TimeEntry):
        print(
            f"logged {kind} activity {activity_id}: {entry.hours} h {entry.category}"
            f" ({entry.person}) on {entry.date.isoformat()}"
        )
    else:
        print(
            f"logged {kind} activity {activity_id}: ${entry.amount_usd} {entry.category}"
            f" on {entry.date.isoformat()}"
        )
    return EXIT_OK


def _run_log_time(args: argparse.Namespace) -> int:
    """Record founder or developer hours for a day, or void an earlier entry (R-30)."""
    return _run_entry(args, events.TIME_KIND, "hours")


def _run_log_cost(args: argparse.Namespace) -> int:
    """Record spend for a day, or void an earlier entry (R-30)."""
    return _run_entry(args, events.COST_KIND, "amount")


def _add_prospects_import_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the prospects-import command's arguments."""
    parser.add_argument(
        "file", type=Path, help="research records: a .json array or a .csv with a header row"
    )
    parser.add_argument(
        "--actor",
        default=inbound.DEFAULT_ACTOR,
        help=f"who imports it (default: {inbound.DEFAULT_ACTOR})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            f"config file with the review checklists (default: ${config.CONFIG_ENV_VAR}, else"
            f" {config.DEFAULT_CONFIG_PATH}; without one, no checklist answers are accepted)"
        ),
    )


def _import_review_config(path: Path | None) -> config.ReviewConfig:
    """The review settings (checklists, max evidence age) for prospects-import and review.

    An explicit --config must load. Without one, a missing default config file means no
    checklist items are configured, so imports without checklist answers keep working.
    """
    if path is None and not config.default_config_path().exists():
        return config.ReviewConfig()
    return config.load_config(path).review


def _run_prospects_import(args: argparse.Namespace) -> int:
    """Validate and import research records; refuse each invalid record by name (R-5, R-6)."""
    path: Path = args.file
    try:
        review_config = _import_review_config(args.config)
        raw_records = validate.load_records(path)
    except (config.ConfigError, validate.FileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    today = events.denver_today()
    keys = review_config.keys()
    records = [validate.validate_record(raw, today, keys) for raw in raw_records]
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        conn = db.connect(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        result = prospects.import_records(conn, path.name, records, args.actor)
    except sqlite3.Error as exc:
        print(f"error: could not import into the database: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    for outcome in result.outcomes:
        stream = sys.stderr if outcome.rejection is not None else sys.stdout
        print(outcome.line(), file=stream)
        for line in outcome.difference_lines():
            print(line)
    print(result.summary())
    return EXIT_REFUSED if result.rejected else EXIT_OK


def _add_set_eligibility_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the set-eligibility command's arguments."""
    parser.add_argument("contact", type=int, help="contact id")
    parser.add_argument("eligibility", choices=eligibility.VALUES, help="the new eligibility")
    parser.add_argument(
        "--source-url",
        default=None,
        help="public professional page showing the address (required for eligible)",
    )
    parser.add_argument(
        "--actor",
        default=events.DEFAULT_ACTOR,
        help=f"who sets it (default: {events.DEFAULT_ACTOR})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"database file (default: ${db.DB_ENV_VAR}, else {db.DEFAULT_DB_PATH})",
    )


def _run_set_eligibility(args: argparse.Namespace) -> int:
    """Change a contact's eligibility, or refuse naming every failed check (R-8, R-24)."""
    db_path: Path = args.db if args.db is not None else db.default_db_path()
    try:
        conn = db.connect(db_path)
    except db.MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        change = eligibility.set_eligibility(
            conn, args.contact, args.eligibility, args.source_url, args.actor, timeutil.utc_now()
        )
    except eligibility.ContactNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except eligibility.EligibilityError as exc:
        for field, rule in exc.failures:
            print(f"error: {field}: {rule}", file=sys.stderr)
        return EXIT_REFUSED
    except sqlite3.Error as exc:
        print(f"error: could not update the database: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    print(change.line())
    return EXIT_OK


def _add_mark_reviewed_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the mark-reviewed command's arguments."""
    parser.add_argument("lead", type=int, help="lead id (a direct candidate or partner prospect)")
    parser.add_argument("result", choices=hand_review.RESULTS, help="the hand-review result")
    parser.add_argument("--reviewer", required=True, help="who reviewed the record")
    parser.add_argument(
        "--date", default=None, help="the review day, YYYY-MM-DD (Denver; default today)"
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="void the lead's earlier hand review and record this one instead",
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


def _run_mark_reviewed(args: argparse.Namespace) -> int:
    """Record one hand-review result the report counts per motion (R-11)."""
    try:
        day = hand_review.parse_review_date(args.date, events.denver_today())
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
        recorded = hand_review.mark_reviewed(
            conn,
            args.lead,
            args.result,
            args.reviewer,
            day,
            args.replace,
            args.actor,
            timeutil.utc_now(),
        )
    except events.EventError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except sqlite3.Error as exc:
        print(f"error: could not record the review: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    finally:
        conn.close()
    print(recorded.line())
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
    Command(
        "log-time",
        "Record founder or developer hours for a day, or void an entry.",
        _add_log_time_arguments,
        _run_log_time,
    ),
    Command(
        "log-cost",
        "Record spend for a day, or void an entry.",
        _add_log_cost_arguments,
        _run_log_cost,
    ),
    Command(
        "report",
        "Print or write the Markdown weekly report for a period of America/Denver dates.",
        _add_report_arguments,
        _run_report,
    ),
    Command(
        "prospects-import",
        "Import researched direct candidates and relationship prospects from JSON or CSV.",
        _add_prospects_import_arguments,
        _run_prospects_import,
    ),
    Command(
        "set-eligibility",
        "Set a contact's eligibility: eligible needs a public source URL and a clear identity.",
        _add_set_eligibility_arguments,
        _run_set_eligibility,
    ),
    Command(
        "mark-reviewed",
        "Record the hand-review result of a researched lead: relevant, irrelevant or fabricated.",
        _add_mark_reviewed_arguments,
        _run_mark_reviewed,
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
