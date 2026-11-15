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
- [ ] With 'cottonwood backup' removed from a copy of the Deletion requests section, the test fails (shown by a mutant run).

## Depends on
_None._
