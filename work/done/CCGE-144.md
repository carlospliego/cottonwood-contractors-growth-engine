# CCGE-144 — prepare-outreach cannot see existing drafts, so a second run reuses draft number 1

## Goal
Let the drafting skill find the next unused LEAD-N without widening it to other folders, so a second run never overwrites an earlier (possibly approved) draft (review 20261115-193520 F-correctness-1).

## Inputs
.claude/skills/prepare-outreach/SKILL.md allowed-tools and Output section,cottonwood/review.py lead_export,tests/test_outreach_skill.py

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Either the lead export gains a next_draft key (a test in tests/ shows it is 1 with no files under the drafts folder and 3 when ID-1.md and ID-2.md exist) and SKILL.md tells the skill to use it, or SKILL.md allowed-tools gains exactly Read(out/drafts/**) and the skill text says to read existing drafts before numbering; either way tests/test_outreach_skill.py's allowed-tools assertion matches the chosen set and uv run pytest passes.
- [x] The changes to existing test `tests/test_review_lead_export.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: the lead export gains a next_draft key (CCGE-144), so the exact top-level key set this test pins gains it).

All criteria verified 2026-11-16.

## Depends on
_None._
