# CCGE-033 — A local --received time inside the spring-forward gap is accepted and stored as a different wall-clock time

## Goal
After converting, convert back to Denver and compare the wall-clock time with the input. Raise ValueError when they differ.

## Inputs
cottonwood/timeutil.py:42-47,review finding F-correctness-1 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] After converting, convert back to Denver and compare the wall-clock time with the input. Raise ValueError when they differ. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
