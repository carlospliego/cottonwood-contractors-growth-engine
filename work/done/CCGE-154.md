# CCGE-154 — hand_review and send call events' public helper names, not the underscored ones

## Goal
CCGE-126 gave events public names for the helpers other modules use, so their contract is explicit, but hand_review.py and send.py still call events._parse_entry_date, _voided_sql, _insert_activity, _day_start and _is_http_url. A change to an underscored helper should not be able to break another module unnoticed.

## Inputs
cottonwood/events.py (public aliases at the end), cottonwood/hand_review.py, cottonwood/send.py; follow-up from CCGE-126

## Constraints
No behaviour change. Keep the underscored definitions (other callers and tests use them).

## Plan
1. Add a public is_http_url alias in events.py next to the others.
2. Switch hand_review.py and send.py to the public names.
3. Add a test that no module in cottonwood/ other than events.py references events._<name>.

## Acceptance Criteria
- [x] No file in cottonwood/ other than events.py contains the text `events._` followed by a letter, and a test in tests/ asserts that by scanning the package source.
- [x] events.py exposes is_http_url as a public name, and uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-24.

## Depends on
_None._
