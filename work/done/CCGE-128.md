# CCGE-128 — Test standing_verification skips malformed and other-claim payloads

## Goal
Pin that claims.standing_verification ignores claim_verified rows for another claim id and rows whose payload is malformed or lacks verified_by/verified_at, returning the latest matching valid row.

## Inputs
cottonwood/claims.py:110-128 (standing_verification),review finding F-testing-4 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test inserts claim_verified rows for 'other-claim', one with payload '{"claim_id": "service-area"}' (no verifier) and one valid for 'service-area', and asserts standing_verification(conn, 'service-area') returns the valid row's id, verified_by and verified_at.
- [x] With only the other-claim and the malformed rows present, standing_verification(conn, 'service-area') returns None.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
