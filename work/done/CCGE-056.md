# CCGE-056 — log-event command for the R-15 event types

## Goal
Record every R-15 event on a lead with its time, actor and optional note as one append-only activity (R-15), with log-inbound's failure conventions.

## Inputs
Spec: `work/specs/events-and-stages/spec.md` (AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-6.1),Plan: `work/specs/events-and-stages/plan.md`

## Constraints
A missing lead raises LeadNotFoundError(EventError) whose str is 'no lead <id>', so the CLI prints 'error: no lead 999'; other EventErrors print 'error: <field>: <message>' (build assumption 14).,A blank or whitespace-only --actor is refused with 'actor: must not be empty', like log-inbound.,Only --at, --note, --actor and --db in this task; --stage, --need, --procurement-url and --voids come with CCGE-057/058.

## Plan
Add cottonwood/events.py: EVENT_TYPES (the 12 R-15 types in spec order), EventError(field, message) like inbound.InquiryError, RawEvent (lead_id, type, at, note, actor) and frozen Event, validate_event(raw, now) using timeutil.parse_received for --at and refusing a time later than now (field 'at'), stripping blank note to None and requiring a note for type 'note'.,Add log_event(conn, event) -> int: in one transaction, refuse a missing lead with LeadNotFoundError (CLI prints 'error: no lead <id>'), insert one activity (lead_id, contact_id NULL, type, payload {event, note?}, actor, occurred_at, recorded_at=utc_now()); rollback on any exception.,Register log-event in cli.COMMANDS: positional lead_id (int) and type (choices EVENT_TYPES), --at required, --note, --actor (default inbound.DEFAULT_ACTOR), --db; validate before connect; catch db.MigrationError, EventError and sqlite3.Error -> exit 1 'error: ...'; success prints 'logged <type> activity <id> for lead <lead> at <display_local>'.,Add tests/test_events.py covering every type, the Z form, missing/unparseable/future --at, unknown type (exit 2), unknown lead, note rules, the output line, and a missing DB and an unmigrated empty file (exit 1, 'error:' on stderr, no traceback, no tables created).

## Acceptance Criteria
- [x] For each of the 12 R-15 types (note with --note), `cottonwood log-event 1 TYPE --at "2026-11-16 09:30"` on a migrated database whose lead 1 is an inbound lead exits 0 and appends exactly one activity of that type for the lead with occurred_at 2026-11-16T16:30:00Z, actor 'developer' (or the --actor value) and a non-empty recorded_at; the lead's stage is unchanged.
- [x] `--at 2026-11-16T16:30:00Z` stores occurred_at 2026-11-16T16:30:00Z; a missing --at exits 2, an unparseable --at or a time later than now (e.g. 2999-01-01 00:00) exits 1, and a type outside the R-15 list exits 2; none of these writes an activity.
- [x] Lead id 999 with no row exits 1 with stderr containing 'error: no lead 999' and writes nothing; type note without --note or with whitespace-only --note exits 1 and writes nothing; --note on another type is stored as payload.note.
- [x] The success line printed on stdout contains the new activity id, the type, the lead id and the America/Denver time as shown by timeutil.display_local.
- [x] Against a missing database path and against an empty (unmigrated) file, log-event exits 1 with stderr starting 'error:' and containing no 'Traceback', and the empty file still has no tables afterwards.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
