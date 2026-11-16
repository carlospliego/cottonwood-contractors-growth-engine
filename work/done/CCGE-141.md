# CCGE-141 — review --lead --json: export one lead for the drafting skill

## Goal
Export everything the drafting skill may use about one lead, and no email address, with whether a draft may be written (R-20, R-24).

## Inputs
Spec: `work/specs/outreach-skill/spec.md` (AC-1.1, AC-1.2, AC-1.3, AC-4.1)
Plan: `work/specs/outreach-skill/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/review.py: LeadExportError(field, message); lead_export(conn, lead_id, settings, claims_path) -> dict with lead_id, type, stage, organization {name, domain}, contact {id, name, role, eligibility, suppressed} or null, verified_facts (list), hypothesis, evidence [{url, observed_at, published_at, kind, excerpt, observation}], checklist (answers per configured item), claims [{id, text, status}] from claims.effective_statuses, sending {sender_identity, postal_address, opt_out_line, ad_identification}, draftable, blocked_by (no_contact_email, suppressed). Never copy contacts.email, email_norm or phone.
2. cottonwood/cli.py: review gains --lead INT, --json, --claims PATH (default claims.DEFAULT_CLAIMS_PATH); --lead without --json is a usage error (exit 2); unknown lead exits 1 'error: lead: ...'; --out writes the JSON and prints 'lead export written: PATH'.
3. tests/test_review_lead_export.py.

## Acceptance Criteria
- [x] With utc_now pinned to 2026-12-01T00:00:00Z and a direct_candidate lead 1 whose contact has name, role, email Pat@Firm.example.com and eligibility eligible, plus verified facts, a hypothesis, one evidence row, a claims file with one claim and a config with four sending values, 'cottonwood review --lead 1 --json --claims CLAIMS' exits 0 and prints one JSON object whose keys are exactly lead_id, type, stage, organization, contact, verified_facts, hypothesis, evidence, checklist, claims, sending, draftable and blocked_by; contact has keys id, name, role, eligibility and suppressed; each claims item has id, text and status equal to its effective status; sending holds the four configured values; draftable is true, blocked_by is [], and no string anywhere in the output contains '@'.
- [x] After 'cottonwood suppress pat@firm.example.com --reason asked', the same export has draftable false and blocked_by containing suppressed and contact.suppressed true; for a lead 2 with no contact the export has contact null, draftable false and blocked_by containing no_contact_email; both exit 0; adding '--out OUT/lead.json' writes the same JSON object to that file and prints 'lead export written: OUT/lead.json'.
- [x] 'cottonwood review --lead 99 --json' with no lead 99 exits 1 with a stderr line starting 'error: lead:', and 'cottonwood review --lead 1' without --json exits 2; plain 'cottonwood review' output is unchanged (the existing review tests pass).
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
