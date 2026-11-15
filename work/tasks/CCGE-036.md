# CCGE-036 — Companies whose names normalize to an empty string all reuse one organization

## Goal
In validate(), treat a company whose normalize_name is empty as not supplied, or reject it with InquiryError('company', ...).

## Inputs
cottonwood/inbound.py:140-152,review finding F-correctness-4 (run 20261115-041840)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] In validate(), treat a company whose normalize_name is empty as not supplied, or reject it with InquiryError('company', ...). A test (or, for documentation-only findings, a check of the changed text) demonstrates the behaviour described, and uv run pytest, ruff check, mypy and ruff format --check pass.

## Depends on
_None._
