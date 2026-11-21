# CCGE-003 — Verify each migration's transaction and version bump after it runs

## Goal
A migration file whose SQL contains its own COMMIT/BEGIN or otherwise breaks the wrapped script cannot leave the database half-applied or at the wrong user_version without an error.

## Inputs
cottonwood/db.py:_apply (review finding F-correctness-2, run 20261115-023924); cottonwood/db.py migrate() (~L147-168, autocommit=True connection); cottonwood/cli.py _run_migrate (MigrationError -> 'error: <msg>', EXIT_REFUSED); tests/test_migrate.py (test_failed_migration_rolls_back_and_keeps_version is the model); cottonwood/migrations/002_core.sql (CREATE TRIGGER ... BEGIN ... END bodies must still pass).

## Constraints
Decided 2026-11-19 (developer): transaction control is caught by scanning the file before it runs, not after. The file is split into statements (sqlite3.complete_statement, so trigger BEGIN...END bodies stay inside their CREATE TRIGGER statement) and any statement whose first keyword, after leading -- and /* */ comments, is BEGIN, COMMIT, END, ROLLBACK, SAVEPOINT or RELEASE is refused with MigrationError naming the file, before BEGIN IMMEDIATE, so the database is untouched. Decided 2026-11-19 (developer): the AC1 CLI test monkeypatches db.migrate (as cli sees it) with a wrapper that passes a tmp migrations folder; no change to how migrate() resolves its folder. Shipped migrations must still apply unchanged. Errors follow the existing 'migration <file> failed: ...' / MigrationError convention. No existing test is changed.

## Plan
1. db.py: add a helper that splits migration SQL into statements and finds transaction-control statements; call it in _apply before BEGIN IMMEDIATE and raise MigrationError naming the file.
2. db.py _apply: after executescript, raise MigrationError naming the file if conn.in_transaction is true or user_version(conn) != migration.number.
3. tests/test_migrate.py (new tests only): COMMIT mid-file through `cottonwood migrate` exits 1, stderr names the file, user_version stays at the previous number; trigger BEGIN...END still applies; post-checks tested with a forced in-transaction state and a forced version mismatch.
4. Run all checks.

## Acceptance Criteria
- [x] A test with a migration file containing `COMMIT;` mid-file shows `cottonwood migrate` exits 1 with an error naming that file, and user_version stays at the previous migration's number.
- [x] After a successful migration, the runner asserts the connection is not in a transaction and user_version equals the migration number; a test covers both checks.

All criteria verified 2026-11-19.

## Depends on
_None._
