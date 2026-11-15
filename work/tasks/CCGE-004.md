# CCGE-004 — Reject a migration numbered 000 with a specific message

## Goal
A 000_*.sql file is refused at discovery with a message that says numbering starts at 001.

## Inputs
cottonwood/db.py:discover_migrations (review finding F-correctness-4, run 20261115-023924; the gap check from F-correctness-7 already refuses it as '001 is missing')

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A test with only `000_x.sql` in the migrations folder shows discover_migrations raises MigrationError whose message contains `000_x.sql`.

## Depends on
_None._
