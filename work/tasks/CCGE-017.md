# CCGE-017 — normalize_domain strips www. only when a dotted host remains

## Goal
normalize_domain removes a leading 'www.' only if what remains still contains a dot, so hosts like 'www.io' stay valid.

## Inputs
cottonwood/normalize.py:59-62,review finding F-correctness-7 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test asserts normalize_domain('www.io') == 'www.io' and normalize_domain('https://www.example.com') == 'example.com'.

## Depends on
_None._
