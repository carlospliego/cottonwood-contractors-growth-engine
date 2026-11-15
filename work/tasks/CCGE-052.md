# CCGE-052 — Duplicate-refusal tests rely on stdin not being a terminal and would block under pytest -s

## Goal
monkeypatch sys.stdin.isatty to return False in the non-tty refusal tests, so they assert the non-terminal branch explicitly.

## Inputs
tests/test_inbound_duplicates.py:67-87,review finding F-testing-7 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] monkeypatch sys.stdin.isatty to return False in the non-tty refusal tests, so they assert the non-terminal branch explicitly. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
