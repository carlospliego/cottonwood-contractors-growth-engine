"""record-run: one Claude skill run with its version, model, times, files and cost (R-26).

Each run is one ``agent_runs`` row. A cost, when given, comes from a named source (Claude Code's
``/cost`` output or the billing console) and is marked estimated when it is not exact. On a
subscription plan there may be no figure at all: tokens and cost are then left out and stored as
NULL (unknown), never as 0. The weekly report sums the known costs against the monthly cap; the
cap is a record, never enforced.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from decimal import Decimal

from cottonwood import timeutil

VALIDATIONS = ("passed", "failed")
COST_SOURCES = ("claude-code-cost", "billing-console")
COST_MAX_PLACES = 4
TOKENS_MAX = 2**63 - 1  # SQLite INTEGER ceiling

_WHOLE_NUMBER = re.compile(r"^[0-9]+$")
_PLAIN_COST = re.compile(r"^[0-9]+(?:\.([0-9]+))?$")


class RunError(ValueError):
    """A record-run field failed a check; ``field`` names it."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


@dataclass(frozen=True)
class RunRecord:
    """One checked skill run, ready to store."""

    skill: str
    skill_version: str
    model: str
    started_at: str
    ended_at: str
    input_ref: str
    output_ref: str
    validation: str
    tokens: int | None
    cost_usd: str | None
    cost_source: str | None
    cost_estimated: bool | None

    def line(self, run_id: int) -> str:
        """What record-run prints; a missing figure is named as not recorded."""
        if self.cost_usd is None:
            cost = "cost not recorded"
        else:
            source = f"{self.cost_source}, estimated" if self.cost_estimated else self.cost_source
            cost = f"{self.cost_usd} USD ({source})"
        tokens = ", tokens not recorded" if self.tokens is None else ""
        return f"run {run_id} recorded: {self.skill} {self.skill_version}, {cost}{tokens}"


def cost_flag_conflict(cost: str | None, cost_source: str | None, estimated: bool) -> str | None:
    """The usage error for cost flags given without each other, or None when they agree.

    --cost-source and --estimated describe a cost, so they need --cost; a cost needs its source.
    """
    if cost is None:
        if cost_source is not None:
            return "--cost-source needs --cost"
        if estimated:
            return "--estimated needs --cost"
        return None
    if cost_source is None:
        return "--cost needs --cost-source"
    return None


def _required(field: str, value: str) -> str:
    text = value.strip()
    if not text:
        raise RunError(field, "must not be empty")
    return text


def _time(field: str, value: str) -> str:
    try:
        return timeutil.parse_received(value)
    except ValueError as exc:
        raise RunError(field, str(exc)) from None


def parse_tokens(value: str) -> int:
    """A non-negative whole number of tokens."""
    text = value.strip()
    if not _WHOLE_NUMBER.match(text):
        raise RunError("tokens", f"must be a whole number of 0 or more, got {value!r}")
    number = int(text)
    if number > TOKENS_MAX:
        raise RunError("tokens", f"must be at most {TOKENS_MAX}, got {value!r}")
    return number


def parse_cost(value: str) -> str:
    """A plain non-negative USD decimal with at most 4 places, kept as the exact text."""
    text = value.strip()
    match = _PLAIN_COST.match(text)
    if match is None:
        raise RunError("cost", f"must be a plain decimal like 3.25 (USD, 0 or more), got {value!r}")
    places = match.group(1)
    if places is not None and len(places) > COST_MAX_PLACES:
        raise RunError("cost", f"at most {COST_MAX_PLACES} decimal places, got {value!r}")
    return str(Decimal(text))


def build_record(
    *,
    skill: str,
    skill_version: str,
    model: str,
    started: str,
    ended: str,
    input_ref: str,
    output_ref: str,
    validation: str,
    tokens: str | None,
    cost: str | None,
    cost_source: str | None,
    estimated: bool,
    now: str,
) -> RunRecord:
    """Check every field (in option order) and return the run, or raise RunError.

    A missing ``tokens`` or ``cost`` stays None (unknown); with no cost, the source and the
    estimated mark are None too. Callers check :func:`cost_flag_conflict` first.
    """
    name = _required("skill", skill)
    version = _required("skill-version", skill_version)
    model_name = _required("model", model)
    started_at = _time("started", started)
    ended_at = _time("ended", ended)
    if timeutil.parse_utc(started_at) > timeutil.parse_utc(now):
        raise RunError("started", "is later than now")
    if timeutil.parse_utc(ended_at) > timeutil.parse_utc(now):
        raise RunError("ended", "is later than now")
    if timeutil.parse_utc(ended_at) < timeutil.parse_utc(started_at):
        raise RunError("ended", "is earlier than --started")
    input_text = _required("input", input_ref)
    output_text = _required("output", output_ref)
    if validation not in VALIDATIONS:
        raise RunError("validation", f"must be one of {', '.join(VALIDATIONS)}")
    token_count = None if tokens is None else parse_tokens(tokens)
    cost_text: str | None = None
    source: str | None = None
    cost_estimated: bool | None = None
    if cost is not None:
        cost_text = parse_cost(cost)
        if cost_source not in COST_SOURCES:
            raise RunError("cost-source", f"must be one of {', '.join(COST_SOURCES)}")
        source = cost_source
        cost_estimated = estimated
    return RunRecord(
        skill=name,
        skill_version=version,
        model=model_name,
        started_at=started_at,
        ended_at=ended_at,
        input_ref=input_text,
        output_ref=output_text,
        validation=validation,
        tokens=token_count,
        cost_usd=cost_text,
        cost_source=source,
        cost_estimated=cost_estimated,
    )


def record_run(conn: sqlite3.Connection, record: RunRecord) -> int:
    """Insert one agent_runs row in its own transaction and return its id."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            "INSERT INTO agent_runs (skill, skill_version, model, started_at, ended_at,"
            " input_ref, output_ref, validation, tokens, cost_usd, cost_source, cost_estimated)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.skill,
                record.skill_version,
                record.model,
                record.started_at,
                record.ended_at,
                record.input_ref,
                record.output_ref,
                record.validation,
                record.tokens,
                record.cost_usd,
                record.cost_source,
                None if record.cost_estimated is None else int(record.cost_estimated),
            ),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return int(cursor.lastrowid or 0)
