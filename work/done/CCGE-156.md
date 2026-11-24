# CCGE-156 — The inbound report counts a channel or segment it does not know instead of dropping it

## Goal
leads.channel and leads.segment have no CHECK constraint, so a value entered by SQL or a restore (e.g. channel 'fax') is counted in the inbound total but appears under no channel or segment, and the per-channel lines no longer add up to the total with nothing saying why.

## Inputs
cottonwood/report.py _inbound and the inbound lines in the text report, cottonwood/inbound.py CHANNELS and SEGMENTS, cottonwood/migrations/002_core.sql; follow-up from CCGE-046

## Constraints
Known channels and segments keep their lines and order. No schema change.

## Plan
1. In _inbound, count a channel or segment outside the known lists under 'other'.
2. Show the 'other' line only when it is above zero.
3. Test with a directly inserted inbound lead whose channel is 'fax' and segment is 'industrial'.

## Acceptance Criteria
- [x] A test in tests/ inserts an inbound lead with channel 'fax' and segment 'industrial' directly in SQL and shows the report's per-channel counts and per-segment counts each sum to its inbound total, with the unknown value counted under 'other'.
- [x] A report with only known channels and segments prints no 'other' line, and uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-24.

## Depends on
_None._
