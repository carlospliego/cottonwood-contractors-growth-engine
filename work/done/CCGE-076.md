# CCGE-076 — Assert the log-time and log-cost confirmation lines

## Goal
Cover the stdout line each log-time/log-cost write and void prints (review 20261115-091006 F-testing-3).

## Inputs
cottonwood/cli.py:526-538 (F-testing-3)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test asserts the stdout line of a time entry, a cost entry and a void, including the activity id, amount, category, date and (for time) person.

All criteria verified 2026-11-21.

## Depends on
_None._
