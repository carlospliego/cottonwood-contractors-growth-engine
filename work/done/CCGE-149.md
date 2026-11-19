# CCGE-149 — Evidence age uses the publication date when known

## Goal
The max-evidence-age rule (R-10) is meant to stop outreach based on stale signals, but today evidence age is measured from when the developer read the page (observed_at), not when the source was published. A news article published two years ago and read today has age 0 and passes prepare-send. Found in the 2026-11-17 simulation: a KSL article published 2026-10-13 showed age 0. Age must reflect the source's date whenever it is known.

## Inputs
cottonwood/send.py _evidence_check (~L263-295: SELECT MAX(substr(observed_at,1,10))). cottonwood/review.py _queue (~L180-220: newest evidence ORDER BY observed_at) and _evidence_age (~L223). evidence table: observed_at NOT NULL, published_at nullable (cottonwood/migrations/002_core.sql). .claude/skills/research-prospects/SKILL.md procedure and rules. Existing tests: tests/test_prepare_send*.py, tests/test_review_candidates.py, tests/test_research_skill.py.

## Constraints
No schema migration. Do not change how observed_at is stored or validated. An evidence item's effective date is published_at (first 10 chars, YYYY-MM-DD) when present and a valid date, else observed_at. Keep the existing refusal check name 'evidence'. Tests use labeled synthetic fixtures only; no network.

## Plan
1. Add one helper (e.g. in review.py or a small shared function) that returns a lead's newest effective evidence date and the URL of that evidence: COALESCE(published_at, observed_at) per item, max across the lead's evidence.
2. Use it in review._queue so the Evidence URL and Evidence age columns reflect the newest effective date.
3. Use it in send._evidence_check; the refusal message names the date and whether it is the published or observed date, e.g. 'newest evidence published 2026-07-01 is older than 90 days'.
4. Add to research-prospects SKILL.md: record published_at (YYYY-MM-DD) for an evidence item when the page shows a publication date.
5. Add pytest cases for the ACs; run all checks.

## Acceptance Criteria
- [x] A pytest test creates a lead whose only evidence has published_at 120 days before today and observed_at today, with max_evidence_age_days 90, and asserts prepare-send refuses with an 'evidence' refusal whose message contains the published date.
- [x] A pytest test asserts cottonwood review shows evidence age 120 (flagged as over 90) for that same lead.
- [x] A pytest test asserts that for evidence with no published_at and observed_at today, review shows age 0 and prepare-send records no 'evidence' refusal.
- [x] A pytest test asserts that with two evidence items (one published 200 days ago, one published 10 days ago), review shows age 10 and the URL of the 10-day-old item, and prepare-send records no 'evidence' refusal.
- [x] .claude/skills/research-prospects/SKILL.md instructs recording published_at when the page shows a publication date, and `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-17.

## Depends on
_None._
