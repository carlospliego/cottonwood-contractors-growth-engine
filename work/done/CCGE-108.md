# CCGE-108 — Test --actor, blank actor and sqlite3.Error refusal for set-eligibility and mark-reviewed

## Goal
Cover the actor wiring and the database-error refusal paths of set-eligibility and mark-reviewed, which no test exercises.

## Inputs
cottonwood/cli.py (set-eligibility and mark-reviewed handlers: args.actor, except sqlite3.Error),cottonwood/hand_review.py:63-65 (blank actor),cottonwood/eligibility.py (rollback),review finding F-testing-2 (run code/20261115-173820)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] A test runs 'set-eligibility 1 ineligible --actor founder' and asserts the eligibility_set activity's actor column is 'founder'; another runs 'mark-reviewed 1 relevant --reviewer founder --actor founder' and asserts the hand_review actor is 'founder'.
- [x] A test runs mark-reviewed with --actor '   ' and asserts exit 1, a stderr line starting 'error: actor:' and no new activity.
- [x] A test forces a sqlite3.Error during each command (for example by monkeypatching the module's write to raise sqlite3.OperationalError) and asserts exit 1, stderr starting 'error:' and that the contacts row and activities table are unchanged.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
