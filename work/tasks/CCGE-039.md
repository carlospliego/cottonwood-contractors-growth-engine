# CCGE-039 — Relay opt-out SQL has the operator type email_norm by hand, with no instruction to normalize it

## Goal
Write the example as VALUES (lower(trim('Pat@Example.com')), ...) and add a sentence saying email_norm must be the trimmed, lower-cased address.

## Inputs
docs/runbook.md:188-194,review finding F-correctness-7 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Write the example as VALUES (lower(trim('Pat@Example.com')), ...) and add a sentence saying email_norm must be the trimmed, lower-cased address. A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
