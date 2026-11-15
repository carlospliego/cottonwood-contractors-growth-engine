# CCGE-078 — Test combined and padded --need and --procurement-url payloads

## Goal
Cover the stored payload when both R-16 values are given and when they carry surrounding whitespace (review 20261115-091006 F-testing-5).

## Inputs
cottonwood/events.py:145-146 (F-testing-5)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test logs --stage buyer_need_confirmed with padded --need and --procurement-url values, and one with both valid, and asserts the exact stored payload with stripped values.

## Depends on
_None._
