# CCGE-029 — Same-day duplicate check for log-inbound

## Goal
Warn on an inquiry matching an existing inquiry's normalized email or E.164 phone on the same America/Denver date, and save it only on explicit confirmation (R-2).

## Inputs
Spec: `work/specs/inbound-logging/spec.md` (AC-2.1, AC-2.2, AC-2.3, AC-2.4)
Plan: `work/specs/inbound-logging/plan.md`

## Constraints
_None._

## Plan
1. Add inbound.find_same_day_duplicates(conn, email_norm, phone_e164, received_at) -> list[int]: inbound_inquiry leads joined to contacts on (email_norm = ? OR phone_e164 = ?), filtered in Python to timeutil.local_date(received_at) equal to the new inquiry's local date, ordered by lead id.
2. In the log-inbound handler, after validation and before any write: on matches print 'warning: possible duplicate of lead(s) <ids> received <local date>' to stderr; if --confirm-duplicate, save with duplicate_of=ids; elif sys.stdin.isatty(), prompt 'Save anyway? [y/N] ' via input() and save only on y/yes (case-insensitive, trimmed); else print 'refused: duplicate not confirmed (use --confirm-duplicate)' and exit 1.
3. Add tests/test_inbound_duplicates.py covering email and phone matches, normalization, the cross-midnight local-date case, flag, prompt yes/no and non-TTY refusal.

## Acceptance Criteria
- [x] With an existing inbound inquiry for pat@example.com received 2026-11-16 09:30 local, logging another with --email 'PAT@example.com ' received 2026-11-16 15:00 local on non-interactive stdin prints a warning containing the existing lead id, exits 1 and adds no leads, contacts, organizations or activities rows.
- [x] A match on phone alone ('801.555.0134' vs an existing '(801) 555-0134', same local date) also warns and refuses without confirmation.
- [x] The same duplicate with --confirm-duplicate exits 0, creates the lead, and its inquiry_logged payload has duplicate_of equal to the list of matching lead ids.
- [x] With sys.stdin.isatty() true, answering 'y' or 'YES' to the prompt saves the inquiry (exit 0); answering 'n' or an empty line exits 1 and writes nothing.
- [x] An existing inquiry received 2026-11-16 23:30 local and a new one received 2026-11-17 00:30 local with the same email (same UTC date) produce no warning and save with exit 0; a non-matching email and phone on the same day also save with no warning.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-028
