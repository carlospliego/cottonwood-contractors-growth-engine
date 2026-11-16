# CCGE-105 — mark-reviewed command: hand-review results with reviewer, date and replace

## Goal
Record one counted hand-review result per researched lead with reviewer and date, so the report's existing per-motion hand-review counts and data-quality failures are fed by real reviews.

## Inputs
Spec: `work/specs/prospect-review/spec.md` (AC-2.1, AC-2.2, AC-2.3, AC-2.4)
Plan: `work/specs/prospect-review/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/hand_review.py: HandReviewError(field, message); mark_reviewed(conn, lead_id, result, reviewer, day, replace, actor, now): lead must exist ('no lead N') and be direct_candidate or relationship_prospect ('lead: type'); reviewer non-blank; day a date not after today in Denver; find the lead's counted hand_review (events.COUNTED_ACTIVITIES_SQL); if one exists and not replace -> refuse naming its result and id; if replace, append a correction voiding it; append hand_review with payload {result, reviewer}, occurred_at = start of the Denver day in UTC (events._day_start convention), recorded_at now; one transaction.
2. cli.py: mark-reviewed LEAD {relevant,irrelevant,fabricated} --reviewer NAME [--date YYYY-MM-DD] [--replace] [--actor] [--db]; prints 'lead N: hand review RESULT'.
3. New tests: tests/test_mark_reviewed.py, including report integration through cottonwood report --from/--to.

## Acceptance Criteria
- [x] 'cottonwood mark-reviewed 1 relevant --reviewer founder --date 2026-11-30' on direct_candidate lead 1 exits 0, prints 'lead 1: hand review relevant', and writes one hand_review activity for lead 1 with payload exactly {"result": "relevant", "reviewer": "founder"} whose occurred_at falls on 2026-11-30 in America/Denver; then 'cottonwood report --from 2026-11-30 --to 2026-11-30' output contains '- Hand review direct_candidate relevant: 1' and '- Hand review direct_candidate total: 1'.
- [x] Without --date, with utc_now pinned to 2026-12-01T00:00:00Z, the hand_review occurred_at falls on 2026-11-30 in America/Denver.
- [x] 'mark-reviewed 2 fabricated --reviewer founder --date 2026-11-30' on relationship_prospect lead 2 makes the report for 2026-11-30 contain '- Hand review relationship_prospect fabricated: 1' and '- Data-quality failures: 1'.
- [x] Each of these exits 1 with a stderr line starting 'error:' and writes no activity: an inbound_inquiry lead (stderr contains 'lead: type'); lead 99 that does not exist (stderr contains 'no lead 99'); --reviewer '   '; --date 2026-02-30; --date 2026-12-01 (after today in Denver). A result 'maybe' is refused by argparse with exit 2.
- [x] A second 'mark-reviewed 1 irrelevant --reviewer founder --date 2026-11-30' after the first exits 1 with stderr naming the existing result 'relevant' and its activity id, and writes nothing; with --replace it exits 0, writes a correction whose voids_activity_id is the first hand_review's id and a new hand_review with result irrelevant, and the report for 2026-11-30 shows '- Hand review direct_candidate relevant: 0', '- Hand review direct_candidate irrelevant: 1' and '- Hand review direct_candidate total: 1'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
