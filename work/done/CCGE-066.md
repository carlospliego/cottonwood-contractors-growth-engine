# CCGE-066 — Accept only ASCII digits in hours, amounts and entry dates

## Goal
Make the plain-decimal and date rules reject non-ASCII digits such as Arabic-Indic numerals (review 20261115-091006 F-correctness-5).

## Inputs
cottonwood/events.py _PLAIN_DECIMAL and _ISO_DATE (F-correctness-5)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] log-time with hours '١.٥' and log-cost with a --date written in Arabic-Indic digits each exit 1 and write nothing, asserted by a test.

All criteria verified 2026-11-20.

## Depends on
_None._
