# CCGE-102 — Per-record SAVEPOINT rollback and the prospects-import sqlite3.Error exit path are untested

## Goal
Tests prove that a failure inside one record rolls back only that record, and that a database error exits non-zero with nothing written.

## Inputs
cottonwood/prospects.py:131-143 (SAVEPOINT / ROLLBACK TO / except sqlite3.Error),review 20261115-164502 finding F-testing-1,proposed test .sir/runs/fix/20261115-164502/F-testing-1.regression (could not be proved red because of CCGE-063)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test makes the second of three records fail with a sqlite3 error after its organization insert, and asserts that the other two records' leads exist and no organization row of the failed record remains.
- [ ] A test makes the database raise sqlite3.OperationalError during import and asserts exit code 1, a stderr line starting 'error: could not import into the database', and unchanged row counts in every table.
- [ ] Replacing the ROLLBACK TO statement in cottonwood/prospects.py with a no-op makes the first test fail.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
