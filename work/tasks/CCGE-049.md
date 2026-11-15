# CCGE-049 — --actor is never checked: neither that it is stored nor that a blank one is rejected

## Goal
Add a test that logs with --actor founder and asserts activities.actor == 'founder', and a parametrized case `--actor '  '` that expects exit 1 naming 'actor'.

## Inputs
cottonwood/inbound.py:119-121,review finding F-testing-4 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Add a test that logs with --actor founder and asserts activities.actor == 'founder', and a parametrized case `--actor '  '` that expects exit 1 naming 'actor'. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
