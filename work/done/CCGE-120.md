# CCGE-120 — suppress command: add a normalized address to suppression without a lead

## Goal
Let the developer suppress an email address that belongs to no lead, normalized like every suppression check, leaving an existing entry unchanged, so an opt-out from any channel is honored by import, set-eligibility and the send gate (R-24).

## Inputs
Spec: `work/specs/approvals-and-claims/spec.md` (AC-3.1, AC-3.2, AC-3.3, AC-4.1)
Plan: `work/specs/approvals-and-claims/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/gate.py: SUPPRESS_SOURCE = 'suppress'; SuppressResult(email_norm, added, added_at, reason) with line() ('suppressed EMAIL' or 'EMAIL already suppressed since DENVER_DATE (REASON)'); suppress(conn, email, reason, source, now): normalize.normalize_email, refuse ('email') blank or not exactly one '@' with text on both sides, refuse ('reason') blank reason, then in BEGIN IMMEDIATE read the existing row (report it unchanged) or insert (email_norm, reason, source or SUPPRESS_SOURCE, now).
2. cottonwood/cli.py: suppress Command with positional email, --reason (required), --source, --db.
3. tests/test_suppress.py with utc_now pinned: stored row, --source, already-suppressed line and unchanged row, refusals, and that prospects-import then imports the contact ineligible and set-eligibility refuses eligible.

## Acceptance Criteria
- [x] With utc_now pinned to 2026-12-01T00:00:00Z, 'cottonwood suppress " Alice@Example.COM " --reason "asked by phone"' exits 0, prints 'suppressed alice@example.com', and stores one suppression row with email_norm 'alice@example.com', reason 'asked by phone', source 'suppress' and added_at '2026-12-01T00:00:00Z'; with '--source "phone call"' the row's source is 'phone call'.
- [x] Running 'cottonwood suppress alice@example.com --reason other' when alice@example.com was suppressed at 2026-12-01T00:00:00Z with reason 'asked by phone' exits 0, prints 'alice@example.com already suppressed since 2026-11-30 (asked by phone)', and leaves the suppression row's reason, source and added_at unchanged.
- [x] 'suppress alice@example.com --reason "  "' prints a stderr line starting 'error: reason:', and each of '  ', 'alice', 'a@b@c', '@example.com' and 'alice@' as the address prints a stderr line starting 'error: email:'; each exits 1 and stores no suppression row.
- [x] After 'cottonwood suppress alice@example.com --reason x', 'prospects-import' of a valid direct_candidate record whose contact email is 'ALICE@example.com' imports that contact with eligibility 'ineligible', and 'set-eligibility' of that contact to eligible exits 1.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-118
