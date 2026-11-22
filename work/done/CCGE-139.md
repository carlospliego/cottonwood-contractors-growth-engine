# CCGE-139 — prepare-send order test omits suppression and claims

## Goal
Cover suppression and claims in the every-failure-in-order test (review 20261115-191126 F-testing-4).

## Inputs
tests/test_prepare_send.py test_every_failed_check_is_named_in_order

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test in tests/ makes prepare-send fail all nine checks at once (approval, eligibility, suppression, claims, evidence, sender_identity, postal_address, opt_out, ad_identification) and asserts the prepare_refused payload checks and the stderr check names are exactly that list in that order.

All criteria verified 2026-11-21.

## Depends on
_None._
