# CCGE-022 — Email whitespace error message names the real problem

## Goal
normalize_email reports whitespace anywhere in the address and an empty local part as separate, accurate messages.

## Inputs
cottonwood/normalize.py:20-21,review finding F-maintainability-4 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test asserts normalize_email('jane@exa mple.com') raises ValueError matching 'whitespace' and normalize_email('@example.com') raises ValueError matching 'local part'.

## Depends on
_None._
