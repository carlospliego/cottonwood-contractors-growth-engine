# CCGE-106 — review: direct-candidate and relationship-prospect queues with checklist, evidence age and order

## Goal
Show the founder separate ranked queues of direct candidates and relationship prospects with checklist answers, newest evidence and its age, next action, founder time and hand-review result, ordered by a stated rule.

## Inputs
Spec: `work/specs/prospect-review/spec.md` (AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5, AC-4.3)
Plan: `work/specs/prospect-review/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/review.py: candidate_rows(conn, lead_type) with organization and contact; newest evidence per lead (max observed_at, then highest id); counted hand_review result per lead (events.COUNTED_ACTIVITIES_SQL); order key (-yes, founder_time is None, founder_time or 0, lead id); _candidate_section(title, rows, items, max_age, today) rendering the order line, max-age line, '- KEY: LABEL' legend and table, or the empty line; render_review(conn, generated_at, review_config) appends both sections after the unchanged inbound section.
2. Evidence age = (Denver today - observed_at date).days, 'N (over MAX)' when over.
3. cli.py: review loads the config and passes Config.review.
4. New tests: tests/test_review_candidates.py; keep tests/test_review.py's inbound assertions passing (edit only if a whole-output equality must include the new sections).

## Acceptance Criteria
- [x] cottonwood review output contains '## Inbound inquiries', '## Direct candidates' and '## Relationship prospects' in that order, the inbound section's lines are identical to those produced before this change for the same database, and each candidate section contains the line 'Order: most yes answers first; ties: lower founder time first (unknown last); then lowest lead id.'
- [x] The direct-candidate table header is 'Lead | Organization | Contact | Eligibility | ' followed by the configured direct_candidate item keys in config order, then 'Yes | Evidence URL | Evidence age (days) | Next action | Founder time (h) | Hand review | Label'; a lead with no answer for an item shows 'unknown' in that column, the Yes column shows its count of yes answers, Hand review shows the counted hand_review result or '—', and a test lead shows 'TEST' in Label.
- [x] Three direct candidates with yes counts 2, 3, 2 and founder_time_h 1.5, 4, 0.5 appear in the order: the 3-yes lead, then the 2-yes lead with 0.5, then the 2-yes lead with 1.5; a fourth lead with 2 yes answers and no founder time appears after both 2-yes leads that have one.
- [x] With utc_now pinned to 2026-12-01T00:00:00Z, review.max_evidence_age_days 30, and a lead whose evidence rows were observed 2026-10-01 and 2026-10-30, the row shows the 2026-10-30 evidence URL and '31 (over 30)'; a lead observed 2026-10-31 shows '30'; each candidate section contains 'Max evidence age: 30 days', and with the key unset 'Max evidence age: not configured' and plain day counts.
- [x] Each candidate section lists '- KEY: LABEL' for every configured item of its queue; with no leads of a type the section shows 'No direct candidates.' or 'No relationship prospects.'; 'cottonwood review --out FILE' writes text equal to the printed review.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-103, CCGE-105

## Tests to change
- `tests/test_review.py`
