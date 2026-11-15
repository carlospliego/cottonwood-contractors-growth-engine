# CCGE-034 — --received near year 1 or 9999 escapes validation as an OverflowError traceback

## Goal
Catch OverflowError alongside ValueError in parse_received (or bound the accepted year range), and re-raise it as ValueError.

## Inputs
cottonwood/timeutil.py:47-58,review finding F-correctness-2 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Catch OverflowError alongside ValueError in parse_received (or bound the accepted year range), and re-raise it as ValueError. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
