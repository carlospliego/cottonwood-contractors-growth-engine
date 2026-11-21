# CCGE-109 — Test the review queue fallbacks: unreadable checklist, non-date evidence, unreadable hand-review payload

## Goal
Cover the fallback branches in the review's candidate queues so removing one (and crashing the whole review) fails the suite.

## Inputs
cottonwood/review.py _answers (json.JSONDecodeError / non-dict checklist -> unknown),cottonwood/review.py _evidence_age (ValueError -> '—'),cottonwood/hand_review.py review_result (unreadable payload -> ''),review finding F-testing-1 (run code/20261115-173820),proposed test .sir/runs/fix/20261115-173820/F-testing-1.regression (its red proof failed against the mutant, possibly the CCGE-063 editable-install issue; see CCGE-102)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] tests/test_review_fallbacks.py stores leads.checklist as 'not json' and as '[1, 2]', and asserts every checklist cell of those rows in 'cottonwood review' output is 'unknown' and the Yes cell is '0'.
- [x] The same file stores an evidence row with observed_at 'last week' and asserts that lead's 'Evidence age (days)' cell is '—'; and stores a hand_review activity with payload 'not json' and asserts that lead's Hand review cell is '—'.
- [x] With the try/except around json.loads in review._answers removed (and cottonwood imported from the mutated copy), tests/test_review_fallbacks.py fails.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-21.

## Depends on
_None._
