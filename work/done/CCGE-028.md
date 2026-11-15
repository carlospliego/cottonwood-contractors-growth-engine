# CCGE-028 — log-inbound command with project_scope migration

## Goal
Record a relayed form or phone inquiry as an inbound_inquiry lead holding only the supplied fields (R-1, R-3 label storage).

## Inputs
Spec: `work/specs/inbound-logging/spec.md` (AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5, AC-1.6, AC-1.7)
Plan: `work/specs/inbound-logging/plan.md`

## Constraints
_None._

## Plan
1. Add cottonwood/migrations/003_inbound.sql: ALTER TABLE leads ADD COLUMN project_scope TEXT.
2. Add timeutil.parse_received(value): 'YYYY-MM-DD HH:MM' as America/Denver local (fold=0) or a UTC ISO string ending in Z/+00:00; returns stored UTC via to_utc_iso; ValueError otherwise.
3. Add cottonwood/inbound.py: Inquiry dataclass, validate() (at least one of name/email/phone; normalize_email/normalize_phone; budget as finite Decimal >= 0 stored as str), log_inquiry(conn, inquiry, duplicate_of=()) inserting organization (reuse by name_norm), contact, lead (type inbound_inquiry, stage candidate, value_basis buyer-stated when budget given) and one inquiry_logged activity with payload {channel, segment, is_test, duplicate_of} in one transaction.
4. Register log-inbound in cli.COMMANDS with --channel/--received/--segment required, optional --name --email --phone --company --location --scope --budget --test --actor --db; validation errors print 'error: <field>: ...' and exit 1.
5. Update the newest-version assertions (2 -> 3) in tests/test_migrate.py, tests/test_schema.py and tests/test_runbook_restore.py; add tests/test_inbound.py.

## Acceptance Criteria
- [x] After `cottonwood migrate` on a fresh file, PRAGMA user_version is 3 and PRAGMA table_info(leads) lists a nullable project_scope column (tests/test_inbound.py).
- [x] `cottonwood log-inbound --channel form --received "2026-11-16 09:30" --segment commercial --name "Pat Lee" --email Pat@Example.com` exits 0 and creates one leads row with type inbound_inquiry, stage candidate, channel form, segment commercial, received_at 2026-11-16T16:30:00Z, is_test 0 and NULL project_scope, value_amount, value_basis and property_location; its contact has name 'Pat Lee', email 'Pat@Example.com', email_norm 'pat@example.com' and NULL phone_e164.
- [x] With --phone "(801) 555-0134" --scope "lobby refresh" --budget 25000 --location "Murray, UT" --company "Acme Holdings" the lead stores project_scope 'lobby refresh', value_amount '25000', value_basis 'buyer-stated', property_location 'Murray, UT' and an organization named 'Acme Holdings'; the contact has phone_e164 '+18015550134'; a second inquiry with --company "ACME holdings" reuses the same organization id.
- [x] Each logged inquiry appends exactly one inquiry_logged activity for its lead whose JSON payload has channel, segment and is_test keys and does not contain the name, email, phone, scope or budget values.
- [x] --received 2026-11-16T16:30:00Z stores 2026-11-16T16:30:00Z; omitting --received, --channel or --segment, or passing a channel or segment outside the allowed values, exits non-zero and leaves leads empty.
- [x] An invalid email, an invalid phone, a budget of 'abc' or '-5', an unparseable --received, or no --name/--email/--phone each exit 1 with a stderr message naming the field, and leave leads, contacts, organizations and activities empty.
- [x] --test stores is_test 1 and the printed success message contains TEST; without --test the message does not contain TEST.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-15.

## Depends on
_None._

## Tests to change
- `tests/test_migrate.py`
- `tests/test_schema.py`
- `tests/test_runbook_restore.py`
