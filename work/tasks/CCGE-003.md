# CCGE-003 — Verify each migration's transaction and version bump after it runs

## Goal
A migration file whose SQL contains its own COMMIT/BEGIN or otherwise breaks the wrapped script cannot leave the database half-applied or at the wrong user_version without an error.

## Inputs
cottonwood/db.py:_apply (review finding F-correctness-2, run 20261115-023924)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test with a migration file containing `COMMIT;` mid-file shows `cottonwood migrate` exits 1 with an error naming that file, and user_version stays at the previous migration's number.
- [ ] After a successful migration, the runner asserts the connection is not in a transaction and user_version equals the migration number; a test covers both checks.

## Depends on
_None._
