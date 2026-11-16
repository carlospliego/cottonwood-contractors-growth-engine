# CCGE-121 — Claims loader: refuse a claim id that ends in a newline

## Goal
Make the claim-id check reject an id with trailing whitespace or a newline, so no claim can load that approve claim can never match (R-19).

## Inputs
cottonwood/claims.py:29 (_ID regex uses $),review finding F-correctness-1 (run code/20261115-183829)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] A claims file whose claim id is the YAML block scalar 'service-area' followed by a newline makes 'cottonwood claims --claims FILE' exit 1 with a stderr line naming the claim and 'id:'.
- [ ] The id check uses re.fullmatch (or \Z) so 'service-area' still loads and 'service-area\n' does not.
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
