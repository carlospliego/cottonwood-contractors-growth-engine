# CCGE-008 — Test the unreadable-migration and rollback branches of _apply

## Goal
The error branches of _apply and the --version flag are covered by tests.

## Inputs
cottonwood/db.py:_apply, cottonwood/cli.py --version (review finding F-testing-2, run 20261115-023924)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test writes a non-UTF-8 migration file and asserts `cottonwood migrate` exits 1 with an `error:` line naming it (no traceback).
- [ ] A test shows the connection is not in a transaction after a failed migration.
- [ ] A test asserts `main(["--version"])` returns 0 and prints `cottonwood 0.1.0`.

## Depends on
_None._
