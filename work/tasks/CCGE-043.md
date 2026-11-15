# CCGE-043 — parse_received documents the fall-back fold but not the spring-forward gap, which silently shifts the time

## Goal
Either reject times in the gap (round-trip check) or document that they are shifted forward by an hour; add a test.

## Inputs
cottonwood/timeutil.py:34-47,review finding F-maintainability-2 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Either reject times in the gap (round-trip check) or document that they are shifted forward by an hour; add a test. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
