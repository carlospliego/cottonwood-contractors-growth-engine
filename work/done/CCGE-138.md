# CCGE-138 — prepare-send tests check payload keys but not approval ids or other leads' approvals

## Goal
Assert the draft_prepared payload values and that another lead's approvals never satisfy prepare-send (review 20261115-191126 F-testing-3).

## Inputs
tests/test_prepare_send.py test_a_ready_draft_is_copied_and_recorded,cottonwood/send.py _standing_approvals

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test in tests/ asserts the draft_prepared payload's sha256 equals the draft file's SHA-256 and its lead_approval_id and draft_approval_id equal the ids of the newest unvoided lead and draft approvals; another test shows that with the lead and draft approvals recorded only for lead 2 (same draft bytes), prepare-send for lead 1 exits 1 with check approval.

All criteria verified 2026-11-21.

## Depends on
_None._
