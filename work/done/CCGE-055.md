# CCGE-055 — Review table cells pass inquirer-supplied Markdown links and raw HTML through to the founder's review

## Goal
In _cell also escape Markdown/HTML metacharacters (`[`, `]`, `(`, `)`, `<`, `>`, `!`, backtick, `*`, `_`) or wrap free-text cells in code spans with backticks escaped; add a test with link and HTML payloads.

## Inputs
cottonwood/review.py:80-88,review finding F-security-basics-1 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] In _cell also escape Markdown/HTML metacharacters (`[`, `]`, `(`, `)`, `<`, `>`, `!`, backtick, `*`, `_`) or wrap free-text cells in code spans with backticks escaped; add a test with link and HTML payloads. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

All criteria verified 2026-11-20.

## Depends on
_None._
