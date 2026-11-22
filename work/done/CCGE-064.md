# CCGE-064 — Take the write lock before checking state in log_event, log_correction and void_entry

## Goal
Run the refusal checks and the inserts in one write transaction so two concurrent corrections cannot both void the same activity (review 20261115-091006 F-correctness-1).

## Inputs
cottonwood/events.py:205-240 and log_correction/void_entry (F-correctness-1)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] log_event, log_correction and void_entry start a write transaction (BEGIN IMMEDIATE or equivalent) before their first SELECT, and a test with two connections shows a second void of the same activity is refused while the first holds the transaction.

All criteria verified 2026-11-20.

## Depends on
_None._
