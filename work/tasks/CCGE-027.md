# CCGE-027 — Test email whitespace rejection and domain userinfo stripping

## Goal
Cover the email whitespace check and the userinfo strip in normalize_domain.

## Inputs
cottonwood/normalize.py:20-56,review finding F-testing-6 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] tests/test_normalize.py asserts normalize_email('jane doe@example.com') raises ValueError and normalize_domain('https://user@Example.com/x') == 'example.com'.

## Depends on
_None._
