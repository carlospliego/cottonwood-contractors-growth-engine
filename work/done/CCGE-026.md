# CCGE-026 — Test the international phone length bounds

## Goal
Cover the 8-15 digit bound for non-+1 international numbers in normalize_phone.

## Inputs
cottonwood/normalize.py:40-42,review finding F-testing-5 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] tests/test_normalize.py asserts '+44 20' and '+4412345678901234' each raise ValueError matching 'international numbers'.

All criteria verified 2026-11-20.

## Depends on
_None._
