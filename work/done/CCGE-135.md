# CCGE-135 — A failed sendable write can leave a partial file in the send folder

## Goal
Write the sendable draft so that a failure during the write never leaves a partial or uncertified file in the output folder (review 20261115-191126 F-correctness-3).

## Inputs
cottonwood/send.py prepare_send sendable.write_bytes and its cleanup

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test in tests/ that makes the sendable write raise OSError partway (for example by monkeypatching Path.write_bytes to write some bytes then raise) shows prepare-send exits 1, OUT contains no file named after the draft, and no draft_prepared activity exists.

All criteria verified 2026-11-20.

## Depends on
_None._
