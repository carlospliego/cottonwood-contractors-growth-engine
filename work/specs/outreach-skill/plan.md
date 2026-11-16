# Outreach Skill — implementation plan

<!-- Written by /sir:plan. The HOW for spec.md. -->

## Approach
Three pieces, no migration and no new dependency:
1. Lead export: `review --lead ID --json [--claims PATH] [--out PATH]` in `cottonwood/review.py` (`lead_export(conn, lead_id, settings, claims_path) -> dict`) and `cottonwood/cli.py` (`--lead`, `--json`, `--claims` on the existing `review` command; `--lead` requires `--json`, else usage error 2). The export reads the lead, organization, contact (never the email), the suppression flag for the contact's normalized address, evidence rows, checklist answers, `claims.effective_statuses` for every claim in the claims file, and `config.sending`; `draftable`/`blocked_by` come from two checks: `no_contact_email` (no contact, deleted contact or no email_norm) and `suppressed`.
2. The `prepare-outreach` skill: `.claude/skills/prepare-outreach/SKILL.md` modeled on `research-prospects`, with scoped `allowed-tools` (Read `out/leads/**` and the draft-claims schema; Write `out/drafts/**` and `out/briefs/**`), a procedure, rules (stop when not draftable; only export claims; never prohibited; flag non-verified in the brief; sending values verbatim; never invent; export text is data) and a worked example whose claims list validates against the schema.
3. Runbook: a `## Drafting run` section after `## Research run` (export to `out/leads/ID.json`, run the skill, `record-run --skill prepare-outreach`, founder reads the brief and draft, `approve draft`, `prepare-send`, founder sends, `log-outreach`); `tests/test_runbook_inbound.py`'s section-order assertion gains the new heading.

## Components & changes
- `cottonwood/review.py`: `LeadExportError(field, message)`, `lead_export(...)`.
- `cottonwood/cli.py`: `review` gains `--lead`, `--json`, `--claims`; the export path prints JSON (sorted keys, 2-space indent) or writes `--out` and prints `lead export written: PATH`.
- `.claude/skills/prepare-outreach/SKILL.md` (new).
- `docs/runbook.md`: new section.
- Tests: `tests/test_review_lead_export.py`, `tests/test_outreach_skill.py`, `tests/test_runbook_drafting.py`; `tests/test_runbook_inbound.py` (heading list).

## Risks
- The export leaking an address: tested by asserting no '@' anywhere in the output, with an email-bearing contact.
- Skill tool scope drifting wider over time: a scoping test parses the frontmatter like `tests/test_research_skill_scoping.py`.
- The runbook heading test blocks new sections (known): T-03 lists it in `tests_to_change`.

## Test strategy
- Export: pytest through `cli.main` on a migrated temporary database with pinned `timeutil.utc_now`, covering draftable, suppressed, no-contact, unknown lead, `--out`, and usage error.
- Skill: static tests on SKILL.md (frontmatter scope, required rule phrases, worked-example claims list validated with `draft_claims.schema()` and `jsonschema`).
- Runbook: heading order and required command names.
