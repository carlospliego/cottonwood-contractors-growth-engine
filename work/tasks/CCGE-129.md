# CCGE-129 — Test that a prohibited claim stays prohibited even with an approval on record

## Goal
Pin that effective_statuses reports 'prohibited' with no note for a claim the file marks prohibited, even when a claim_verified activity for it exists (for example recorded before the founder prohibited it).

## Inputs
cottonwood/claims.py:133-137 (effective_statuses prohibited branch),review finding F-testing-5 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test records approve claim service-area, then writes a claims file marking service-area prohibited, and asserts 'cottonwood claims' prints 'service-area: prohibited' and exits 0.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
