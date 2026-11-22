# CCGE-061 — Cover log-time/log-cost write failures and blank actors on --voids (F-testing-2)

## Goal
Make the sqlite3.Error branch of the log-time/log-cost handler and the rollback in _insert_entry/void_entry observable by a test, and cover blank --actor for log-cost and --voids (review 20261115-091006 F-testing-2; the first proposed test passed with the except branch removed, so it proved nothing).

## Inputs
cottonwood/cli.py _run_entry except sqlite3.Error branch (review 20261115-091006 F-testing-2),cottonwood/events.py _insert_entry and void_entry rollback,tests/test_time_cost.py test_blank_actor_is_refused

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test forces an insert failure (for example a BEFORE INSERT trigger raising) for log-time, log-cost and each --voids form and asserts exit 1, stderr starting 'error: could not save the entry', no 'Traceback' and an unchanged activity count; the same test fails when the except sqlite3.Error branch in cottonwood/cli.py _run_entry is removed.
- [x] log-cost with --actor ' ' and log-time/log-cost --voids with --actor ' ' each exit 1 and write nothing, asserted by a test.

All criteria verified 2026-11-20.

## Depends on
_None._
