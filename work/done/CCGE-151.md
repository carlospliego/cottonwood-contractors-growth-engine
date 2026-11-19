# CCGE-151 — research-prospects demand mode: sample-check that a segment's signal means construction work before picking it

## Goal
On 2026-11-18 demand mode picked newly registered dental practices (NPI) as the best opportunity. A follow-up check showed that 4 of the 6 researched practices were already open in existing dental suites (takeovers, rebrands or moves), so they were not build-out leads. Demand mode rated the signal 'high' without checking whether the signal actually means a project Cottonwood could bid. The pick must rest on a sample showing that the signal turns into construction work.

## Inputs
.claude/skills/research-prospects/SKILL.md (Demand mode steps 3-5 and the demand report under Output); out/research/2026-11-18-new-dental-practices.demand.md (follow-up note and lesson); tests/test_research_skill.py (pattern for asserting skill text).

## Constraints
Skill text and its tests only; no code, schema or CLI changes. Keep allowed-tools unchanged (scoping test). Bump the skill version and the after-run --skill-version together (an existing test checks they match).

## Plan
1. In Demand mode, add a rating 'project conversion': for 2 or 3 sampled organizations per candidate, check the organization's own pages or listings for whether the signal means new space or a build-out (new address or new building, 'coming soon', 'ready for improvements') rather than a takeover, rebrand or move into an existing fitted-out space; rate high/medium/low/unknown from that sample only.
2. Make a candidate rated low or unknown on project conversion ineligible to win, like reachability.
3. In the Procedure, before writing a record from a signal like a new registration, check the organization's own site or listing for 'now open' or a takeover of an existing practice at the same address; a record already open in an existing fitted-out space is dropped and listed under Dropped with the reason.
4. Add a 'Project conversion' column to the shortlist table described for the demand report.
5. Bump the version to 1.3.0 in the frontmatter and the after-run step.
6. Add pytest checks for the new text; run all checks.

## Acceptance Criteria
- [x] A pytest test asserts SKILL.md's Demand mode names a 'project conversion' rating checked on a sample of 2 or 3 organizations per candidate, and states that a candidate rated low or unknown on it never wins.
- [x] A pytest test asserts SKILL.md's Procedure tells the researcher to drop a prospect that is already open in an existing fitted-out space (a takeover, rebrand or move), and to list it under Dropped with the reason.
- [x] A pytest test asserts the demand report section of SKILL.md lists a 'Project conversion' column for the shortlist.
- [x] SKILL.md frontmatter version is 1.3.0 and the after-run step says `--skill-version 1.3.0`; allowed-tools is unchanged from CCGE-150's version; `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-18.

## Depends on
CCGE-150
