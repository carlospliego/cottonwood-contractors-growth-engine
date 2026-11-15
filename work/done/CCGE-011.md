# CCGE-011 — Core schema migration with append-only triggers

## Goal
Migration 002_core.sql creates the 7 tables with the R-14 stage rule and the activities/suppression protections, and db.connect() opens connections with foreign keys on.

## Inputs
Spec: `work/specs/data-core/spec.md` (AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5)
Plan: `work/specs/data-core/plan.md`

## Constraints
_None._

## Plan
1. Add cottonwood/migrations/002_core.sql with organizations, contacts, leads, evidence, activities, agent_runs, suppression per architecture.md Interfaces & data; CHECK constraints for lead type, stage per type (R-14), eligibility, evidence kind, is_test 0/1, json_valid(payload); foreign keys; partial unique index on organizations.domain_norm; indexes on contacts.email_norm, contacts.phone_e164, leads.type, activities.lead_id; triggers rejecting UPDATE/DELETE on activities and UPDATE/DELETE on suppression. No BEGIN/COMMIT in the file (the runner wraps it).
2. Add db.connect(db_path) -> sqlite3.Connection: PRAGMA foreign_keys = ON, busy timeout BUSY_TIMEOUT_SECONDS, sqlite3.Row row factory; raise MigrationError-style clear error if the file does not exist.
3. Update the default-migration assertions in tests/test_migrate.py from version 1 / no tables to version 2 / the 7 tables (listed in Tests to change).
4. Add tests/test_schema.py: table and key-column presence; activities UPDATE and DELETE rejected with the row unchanged; suppression DELETE and UPDATE rejected; every allowed type/stage pair inserts and cross-type stages fail; a version-1 database upgrades to 2 and a second migrate applies nothing; foreign keys enforced through connect().
5. Run all checks.

## Acceptance Criteria
- [x] After `cottonwood migrate` on a new file, PRAGMA user_version is 2 and the non-internal tables are exactly activities, agent_runs, contacts, evidence, leads, organizations and suppression; a test asserts it.
- [x] A test asserts each table has the key columns listed in architecture.md Interfaces & data (for example activities has id, lead_id, contact_id, type, payload, actor, occurred_at, recorded_at, voids_activity_id).
- [x] A test shows UPDATE and DELETE on an activities row each raise sqlite3.IntegrityError and the row is unchanged afterwards.
- [x] A test shows DELETE on a suppression row raises sqlite3.IntegrityError and the row is still present.
- [x] A parametrized test inserts a lead for every allowed R-14 type/stage pair successfully, and shows `walkthrough` for relationship_prospect and `introduced` for direct_candidate are rejected.
- [x] A test migrates a database that is at user_version 1 to user_version 2, and a second migrate reports 0 applied.
- [x] db.connect() returns a connection on which PRAGMA foreign_keys is 1, and a test shows inserting a contact with a missing organization_id reference fails.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run mypy .` exit 0.

All criteria verified 2026-11-15.

## Depends on
CCGE-010

## Tests to change
- `tests/test_migrate.py`
