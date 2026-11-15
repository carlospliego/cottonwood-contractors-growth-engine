# CCGE-096 — Re-import difference lines print distinct founder_time_h values identically

## Goal
A founder_time_h difference line shows the stored and incoming values distinguishably.

## Inputs
cottonwood/prospects.py:319-320 (_shown uses {value:g}),review 20261115-164502 finding F-correctness-8

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] Re-importing a matched lead stored with founder_time_h 1234567 using founder_time_h 1234568 prints a line containing "stored '1234567'" and "incoming '1234568'".
- [ ] Stored 2.0 against incoming 2.5 prints "stored '2'" and "incoming '2.5'".
- [ ] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

## Depends on
_None._
