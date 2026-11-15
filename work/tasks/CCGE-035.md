# CCGE-035 — A budget in exponent form is stored and shown in scientific notation

## Goal
Reject input that contains e/E, or format with `format(amount, 'f')`.

## Inputs
cottonwood/inbound.py:72-84,review finding F-correctness-3 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Reject input that contains e/E, or format with `format(amount, 'f')`. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
