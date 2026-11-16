# CCGE-125 — gate.py: remove the unused TEXT_SCOPES constant

## Goal
Delete TEXT_SCOPES from cottonwood/gate.py or use it in the audience/offer branch, so no dead constant suggests a rule that is not enforced.

## Inputs
cottonwood/gate.py:29,review finding F-maintainability-1 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] 'grep -rn TEXT_SCOPES cottonwood tests' finds either no match or a match in the code path that handles the audience and offer scopes.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
