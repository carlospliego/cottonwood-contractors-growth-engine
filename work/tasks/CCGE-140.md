# CCGE-140 — log-reply date refusals and transaction atomicity are untested

## Goal
Test log-reply's --date refusals and that a failure after the reply insert rolls back the reply too (review 20261115-191126 F-testing-6).

## Inputs
cottonwood/send.py log_reply,tests/test_log_reply.py

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] With utc_now pinned to 2026-12-01T00:00:00Z, tests in tests/ show 'log-reply 1 other --date 2026-12-01' and 'log-reply 1 other --date 30/11/2026' exit 1 with stderr starting 'error: date:' and append nothing, and that when the suppression insert for an opt_out raises sqlite3.Error the command exits 1 and no reply activity is stored.

## Depends on
_None._
