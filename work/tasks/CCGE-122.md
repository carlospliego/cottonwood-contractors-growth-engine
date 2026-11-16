# CCGE-122 — approve: refuse a lead id too large for SQLite instead of crashing

## Goal
Refuse 'approve lead N' and '--lead N' for N above 9223372036854775807 with 'error: lead:' and exit 1, instead of an OverflowError traceback.

## Inputs
cottonwood/gate.py:269-281 (_lead_item, _check_lead),cottonwood/cli.py approve --lead type=int,review finding F-correctness-2 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] 'cottonwood approve lead 99999999999999999999 --approver Founder --reference r' exits 1 with a stderr line starting 'error: lead:' and appends no activity.
- [ ] 'cottonwood approve offer x --lead 99999999999999999999 --approver Founder --reference r' exits 1 with a stderr line starting 'error: lead:' and appends no activity.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
