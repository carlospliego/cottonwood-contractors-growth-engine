# CCGE-124 — approve claim: print verified_by and verified_at as YAML that reads back exactly

## Goal
Make the line approve claim prints give verified_by and verified_at in a form that, pasted into config/claims.yaml, loads as the same strings, so an approver name such as 'Yes', '123' or 'Smith: Jo' still matches its claim_verified activity.

## Inputs
cottonwood/gate.py:60-64 (Approval.line for claims),cottonwood/claims.py (_claim verified_by handling),review finding F-correctness-4 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] For each approver 'Founder', 'Yes', '123' and 'Smith: Jo', the verified_by value printed by 'approve claim' (for example as a double-quoted YAML string), written into a claims file as that claim's verified_by with status verified and the printed verified_at, makes 'cottonwood claims' print 'ID: verified' and exit 0.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
