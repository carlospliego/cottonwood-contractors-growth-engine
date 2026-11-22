# CCGE-050 — Budget formatting is not tested beyond an integer: exponent input is stored as '1E+3' and the zero branch i...

## Goal
Parametrize valid budgets ('0', '-0', '0.00', '25000.50', '1e3') with the stored text you expect, and decide whether exponent notation should be normalized or rejected.

## Inputs
cottonwood/inbound.py:72-84,review finding F-testing-5 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Parametrize valid budgets ('0', '-0', '0.00', '25000.50', '1e3') with the stored text you expect, and decide whether exponent notation should be normalized or rejected. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
