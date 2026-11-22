# CCGE-025 — Deletion-section order check fails when the backup step is missing

## Goal
test_deletion_section_backs_up_clears_fields_and_keeps_suppression asserts both phrases are present before comparing their positions.

## Inputs
tests/test_runbook_restore.py:76-78,review finding F-testing-4 (run 20261115-032430)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] With 'cottonwood backup' removed from a copy of the Deletion requests section, the test fails (shown by a mutant run).
- [x] The changes to existing test `tests/test_runbook_restore.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: The contract's goal is to make this exact test assert both phrases are present before comparing positions; the order assertion is kept and strengthened, not weakened).

All criteria verified 2026-11-20.

## Depends on
_None._
