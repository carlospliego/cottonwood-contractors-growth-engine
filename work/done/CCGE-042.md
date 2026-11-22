# CCGE-042 — _parse_budget promises 'exact decimal text' but returns scientific notation for exponent input

## Goal
Format with format(amount, 'f') (or reject exponents) and state the stored format in the docstring; add a test for '1e3'.

## Inputs
cottonwood/inbound.py:72-84,review finding F-maintainability-1 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Format with format(amount, 'f') (or reject exponents) and state the stored format in the docstring; add a test for '1e3'. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
