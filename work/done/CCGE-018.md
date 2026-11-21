# CCGE-018 — display_local formats offsets with seconds correctly

## Goal
display_local renders an offset as ±HH:MM and only appends seconds when the offset has them, instead of slicing the %z string blindly.

## Inputs
cottonwood/timeutil.py:40-44,review finding F-correctness-8 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test formats a datetime in a zone with a sub-minute offset (e.g. America/Denver before 1883, LMT -06:59:56) and asserts the offset text is '-06:59:56', while 2026-01-15T19:00:00Z still shows '-07:00'.

All criteria verified 2026-11-20.

## Depends on
_None._
