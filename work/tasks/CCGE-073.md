# CCGE-073 — Give time and cost validation an accurately named error

## Goal
Stop raising EventError for time and cost entries, which are not events, or document that it covers them (review 20261115-091006 F-maintainability-7).

## Inputs
cottonwood/events.py:62-67 EventError (F-maintainability-7)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] EventError's docstring states it covers time and cost entries, or time and cost validation raises a separately named error that the CLI maps to exit 1, asserted by the existing time/cost refusal tests.

## Depends on
_None._
