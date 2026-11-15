# CCGE-031 — Runbook: inbound verification checklist and relay sections

## Goal
Document the R-4 inbound verification checklist and the relay procedure in docs/runbook.md.

## Inputs
Spec: `work/specs/inbound-logging/spec.md` (AC-4.1, AC-4.2, AC-4.3)
Plan: `work/specs/inbound-logging/plan.md`

## Constraints
_None._

## Plan
1. Remove the line 'Later features add the inbound checklist and relay sections to this file.' from docs/runbook.md.
2. Add '## Inbound verification checklist' with a table: Item | checked_at | result | owner, one row per R-4 item (commercial test submission, residential test submission, spam/blocked-submission path, notification spam-folder check, Formspark account owner/plan/limits/submission retention, auto-forward to the developer, mobile form and phone-link check, missed-call handling and owner, same-working-day response capacity, GA4 vs privacy-page reconciliation), fields left blank to fill in, plus how to log the test submissions with --test and confirm they show as TEST in review.
3. Add '## Relay' describing auto-forwarding (or CC) of Formspark notifications and outreach-mailbox replies to the developer, the founder's daily note for calls and in-person events, same-working-day logging and same-day opt-outs, with example log-inbound commands for a form and a phone inquiry and the duplicate warning.
4. Add tests/test_runbook_inbound.py asserting the headings, each checklist item and its three fields, and the relay statements.

## Acceptance Criteria
- [x] docs/runbook.md has a '## Inbound verification checklist' section whose table has columns checked_at, result and owner and one row for each of: commercial test submission, residential test submission, spam/blocked-submission path, notification spam-folder check, Formspark account owner, plan, limits and submission retention, auto-forward to the developer, mobile form and phone-link check, missed-call handling and owner, same-working-day response capacity, GA4 vs privacy-page reconciliation.
- [x] docs/runbook.md has a '## Relay' section stating that Formspark notifications and outreach-mailbox replies are auto-forwarded (or CC'd) to the developer, that the founder's daily note covers calls and in-person events, that everything is logged the same working day and opt-outs the same day, and containing a `cottonwood log-inbound --channel form` and a `cottonwood log-inbound --channel phone` example, with `--test` shown for checklist submissions.
- [x] docs/runbook.md no longer contains 'Later features add the inbound checklist and relay sections'; the Restore from backup, Re-applying suppression after a restore and Deletion requests sections are byte-for-byte unchanged and tests/test_runbook_restore.py, tests/test_runbook_missing_check.py and tests/test_runbook_restore_hot_journal.py pass.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-028, CCGE-029, CCGE-030
