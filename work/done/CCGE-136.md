# CCGE-136 — send.py duplicates activity insertion and file hashing

## Goal
Use one activity-insert helper and one file-digest helper in cottonwood/send.py instead of _insert_prepared, _insert and inline hashlib calls (review 20261115-191126 F-maintainability-1).

## Inputs
cottonwood/send.py _insert_prepared, _insert, sha256_file and the inline hashlib.sha256 in prepare_send

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] cottonwood/send.py defines no function named _insert_prepared and contains exactly one INSERT INTO activities statement and at most one hashlib.sha256 call; uv run pytest passes.

All criteria verified 2026-11-21.

## Depends on
_None._
