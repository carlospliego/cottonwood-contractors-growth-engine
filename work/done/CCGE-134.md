# CCGE-134 — prepare-send reads its gate checks before taking the write lock

## Goal
Evaluate every R-21 check inside the same BEGIN IMMEDIATE transaction that writes the draft_prepared activity, so an opt-out, approval void or claim change committed meanwhile cannot slip through (review 20261115-191126 F-correctness-1).

## Inputs
cottonwood/send.py prepare_send (checks run before conn.execute('BEGIN IMMEDIATE'))

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] In cottonwood/send.py prepare_send, the calls to _approvals, _contact_checks, _claim_checks and _evidence_check run after conn.execute("BEGIN IMMEDIATE"); a test in tests/ shows that a suppression row inserted by a second connection before the first connection's BEGIN IMMEDIATE makes prepare-send refuse with check suppression.

All criteria verified 2026-11-20.

## Depends on
_None._
