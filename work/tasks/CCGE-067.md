# CCGE-067 — Bound cost amounts so cost totals stay exact

## Goal
Prevent Decimal's 28-digit context from rounding cost totals for very large amounts (review 20261115-091006 F-correctness-6).

## Inputs
cottonwood/events.py validate_cost and cost_totals (F-correctness-6)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] log-cost with an amount above a documented maximum exits 1 and writes nothing, or cost_totals sums in a local Decimal context wide enough that a test summing two 30-digit amounts returns the exact total.

## Depends on
_None._
