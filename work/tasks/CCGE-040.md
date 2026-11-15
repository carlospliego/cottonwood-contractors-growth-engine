# CCGE-040 — Duplicate confirmation crashes with AttributeError when stdin is closed

## Goal
Treat a missing stdin as non-interactive: `if sys.stdin is None or not sys.stdin.isatty(): return False`.

## Inputs
cottonwood/cli.py:146-153,review finding F-correctness-8 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Treat a missing stdin as non-interactive: `if sys.stdin is None or not sys.stdin.isatty(): return False`. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
