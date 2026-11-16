# Prospect Review — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
Imported prospects (feature `prospect-import`) sit in the database as `researched` leads, but nothing lets the developer prove a contact may be emailed, record the hand-review result the Gate 1 evidence check depends on, or show the founder a ranked queue of direct candidates and relationship prospects. Without these the phase-4 exit criteria cannot be met: `set-eligibility` must refuse without a source or for suppressed addresses, `mark-reviewed` counts must feed the report, and `review` must show separate candidate queues with checklist answers, evidence age and the stated order (docs/cottonwood-growth-engine.md R-8, R-10, R-11, R-13, R-24, R-31; SPEC.md §9).

## Goals / non-goals
- Goal: `cottonwood set-eligibility CONTACT eligible|ineligible|unknown` changes a contact's eligibility; `eligible` needs a public professional source URL and an unambiguous identity and is refused for a suppressed address; every change writes an `eligibility_set` activity recording the basis.
- Goal: `cottonwood mark-reviewed LEAD relevant|irrelevant|fabricated --reviewer NAME` records the hand-review result with reviewer and date; the weekly report already counts it per motion and counts `fabricated` as a data-quality failure.
- Goal: `cottonwood review` adds a direct-candidate and a relationship-prospect section after the inbound section, each row showing yes/no/unknown answers to that queue's checklist items from `config/pilot.yaml`, the newest evidence URL and age, next action and founder time, ordered by `yes` count then lower founder time, with the rule stated.
- Goal: checklist answers come from the research record (`checklist` object) so the research skill can supply them; unknown checklist keys are rejected at import.
- Non-goal: `prepare-send`'s evidence-age refusal (R-10's second half) and every other pre-send check (feature `send-gate`).
- Non-goal: `review --lead ID --json` export for the drafting skill (feature `outreach-skill`), the research skill and `record-run` (feature `research-skill`).
- Non-goal: editing checklist answers after import, scoring beyond the yes count, or any probability/ML score (SPEC.md §9).

## User stories
### US-1 — Set contact eligibility with a recorded basis
As the developer, I want to mark a contact eligible only when I have a public professional source and the identity is unambiguous, so that outreach never goes to an unsupported or suppressed address.

Acceptance criteria:
- AC-1.1: For a not-deleted contact 1 with a name and email, eligibility `unknown`, whose email_norm no other not-deleted contact has and is not suppressed, `cottonwood set-eligibility 1 eligible --source-url https://acme.example/team` exits 0, prints `contact 1: eligibility unknown -> eligible`, stores `eligible` and `source_url` `https://acme.example/team` on the contact, and writes one counted `eligibility_set` activity with contact_id 1 whose payload is exactly `{"from": "unknown", "to": "eligible", "basis": "public-source-url"}`.
- AC-1.2: `set-eligibility 1 eligible` exits 1, changes no row and writes no activity, with stderr naming every failed check among: `source-url: required` (no `--source-url`), `source-url: url` (not http(s) with a host), `contact: suppressed` (email_norm in suppression), `contact: deleted` (deleted_at set), `contact: identity` (no name, no email, or another not-deleted contact with the same email_norm).
- AC-1.3: `ineligible` and `unknown` need no `--source-url`; their activity payload basis is `manual`; `unknown` on a suppressed address is refused with `contact: suppressed`, while `ineligible` is allowed; an unknown contact id exits 1 with `error: no contact 99`; setting the value the contact already has exits 0, prints `contact 1: eligibility already eligible`, and writes no activity.

### US-2 — Record hand-review results that feed the report
As the developer, I want to record each researched lead's hand-review result, so that the report shows hand-review counts per motion and fabricated records count as data-quality failures.

Acceptance criteria:
- AC-2.1: `cottonwood mark-reviewed 1 relevant --reviewer founder --date 2026-11-30` on a `direct_candidate` lead exits 0, prints `lead 1: hand review relevant`, and writes one counted `hand_review` activity for lead 1 with occurred_at on 2026-11-30 in America/Denver and payload `{"result": "relevant", "reviewer": "founder"}`; `--date` defaults to today in America/Denver; `cottonwood report --from 2026-11-30 --to 2026-11-30` shows `- Hand review direct_candidate relevant: 1` and `- Hand review direct_candidate total: 1`.
- AC-2.2: `mark-reviewed` of a `relationship_prospect` lead as `fabricated` makes that report show `- Hand review relationship_prospect fabricated: 1` and `- Data-quality failures: 1`.
- AC-2.3: Each of these exits 1 with stderr starting `error:` and writes no activity: an `inbound_inquiry` lead (`lead: type`), an unknown lead id (`no lead 99`), a result other than the three (argparse choices), an empty or blank `--reviewer`, a `--date` that is not a real YYYY-MM-DD date or is after today in America/Denver.
- AC-2.4: A second `mark-reviewed` of a lead that already has a counted `hand_review` exits 1 naming the existing result and activity id; with `--replace` it writes a `correction` voiding the earlier `hand_review` and a new `hand_review`, and the report for a period containing both counts only the new result.

### US-3 — Separate, ordered candidate queues in review
As the founder, I want direct candidates and relationship prospects in separate queues with their checklist answers, evidence age and an explicit order, so that I can see which prospects deserve my time first.

Acceptance criteria:
- AC-3.1: `cottonwood review` output has the sections `## Inbound inquiries`, `## Direct candidates` and `## Relationship prospects` in that order; the inbound section is unchanged; each candidate section contains the line `Order: most yes answers first; ties: lower founder time first (unknown last); then lowest lead id.`
- AC-3.2: Each candidate row has the columns Lead, Organization, Contact, Eligibility, one column per configured checklist item of that queue (headed by the item key), Yes, Evidence URL, Evidence age (days), Next action, Founder time (h), Hand review, Label; a checklist item the lead has no answer for shows `unknown`; Evidence URL and age come from the evidence row with the newest observed_at; Hand review shows the result of the lead's counted `hand_review` or `—`; Label is `TEST` for a test lead.
- AC-3.3: Three direct candidates with yes counts 2, 3, 2 and founder time 1.5, 4, 0.5 are listed in the order: the 3-yes lead, the 2-yes lead with 0.5, the 2-yes lead with 1.5; a lead with no founder time comes after leads with the same yes count that have one.
- AC-3.4: With `review.max_evidence_age_days: 30`, a lead whose newest evidence was observed 31 days before today in America/Denver shows `31 (over 30)` and one at 30 shows `30`; each candidate section states `Max evidence age: 30 days`, or `Max evidence age: not configured` when the key is unset.
- AC-3.5: Each candidate section lists its checklist items as `- KEY: LABEL` lines, and shows `No direct candidates.` / `No relationship prospects.` when it has no leads; `review --out FILE` writes the same text (R-31).

### US-4 — Checklist items in config, answers in research records
As the developer, I want the checklist items kept in `config/pilot.yaml` and their answers carried in research records, so that the founder can read and change the items and the research skill can answer them.

Acceptance criteria:
- AC-4.1: `config/pilot.yaml` has `review.checklists.direct_candidate` (six items from SPEC.md §9: current direct signal, territory and capability fit, identifiable buyer, known timing, accessible to a new GC, legal contact route) and `review.checklists.relationship_prospect` (five items: firm relevance, portfolio/geography, repeat referral potential, professional contact validity, introduction angle), each a `key` and `label`; `load_config` raises ConfigError naming the path for a checklist that is not a list, an item without a non-empty key or label, a key not matching `^[a-z][a-z0-9_]*$`, a duplicate key within a queue, or a `max_evidence_age_days` that is not a positive integer.
- AC-4.2: A research record may carry `checklist`, an object mapping item keys to `yes`, `no` or `unknown`; `prospects-import` stores it on the new lead; a value outside the three is rejected `checklist.KEY: enum`; a key not among the configured items for the record's type is rejected `checklist.KEY: checklist-item`; a CSV column `checklist.KEY` carries the same answer; re-importing a matched lead with a different answer prints a `checklist.KEY differs` line and keeps the stored answers.
- AC-4.3: `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

## Constraints & assumptions
- Activity payloads hold no personal data (no names, emails, phones, URLs), because activities are append-only and a deletion request must be able to clear contact data (R-35); the source URL is stored on the contact row instead, and the `eligibility_set` payload records the basis kind.
- "Unambiguous identity" is checked deterministically: the contact has a name and an email and no other not-deleted contact shares its normalized email.
- A lead has at most one counted hand review; a re-review needs `--replace` and is recorded as a correction plus a new result, so the report never double-counts a lead.
- The checklist items are SPEC.md §9's questions minus "What founder time would this likely take?", which is the founder-time column.
- Evidence age is whole days from the newest `observed_at` to today in America/Denver.
- Migration 005 adds `leads.checklist` (JSON object text); the tests pinning the schema version move to 5.

## Success metrics
- The phase-4 exit criteria for this feature hold: `set-eligibility` refuses without a source or for suppressed addresses; `mark-reviewed` counts feed the report; `review` shows separate candidate queues with checklist, evidence age and the stated order (work/initiatives/cottonwood-growth-engine/roadmap.md, phase 4).

## Open questions
- [Founder, before first send] The maximum evidence age (docs/cottonwood-growth-engine.md:136); `review.max_evidence_age_days` stays unset in `config/pilot.yaml` until the founder decides, and `review` says so.
- [Founder] Whether the checklist wording in `config/pilot.yaml` matches how the founder wants prospects judged; the items start from SPEC.md §9.
