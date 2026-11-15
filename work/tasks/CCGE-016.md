# CCGE-016 — normalize_name keeps word boundaries at hyphens

## Goal
normalize_name replaces punctuation such as hyphens with a space (apostrophes still removed), so 'Mary-Jane' and 'Mary Jane' match.

## Inputs
cottonwood/normalize.py:64-67,review finding F-correctness-5 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test asserts normalize_name('Mary-Jane Smith') == normalize_name('Mary Jane Smith') == 'mary jane smith' and normalize_name("O'Neil") == 'oneil'.

## Depends on
_None._
