# CCGE-147 — Deletion requests remove personal details from activity records (founder decision: Option A)

## Goal
Resolve the R-35/R-17 conflict as decided in the 2026-11-15 founder brief: for a deletion request only, personal details are removed from that contact's activity records, the removal is itself logged without personal data, and the suppression entry is kept. Plan with /sir:plan before building (it changes the spec and an append-only rule).

## Inputs
docs/cottonwood-growth-engine.md R-17 and R-35,docs/runbook.md Deletion requests,cottonwood/db.py,cottonwood/events.py,cottonwood/gate.py

## Constraints
Survey answers (taken as recommendations; the user asked for the whole backlog unattended): (1) the founder brief is not in the repo, so the Goal is the full statement of Option A. (2) A new CLI command `deletion-request --contact <id> [--actor] [--db]` does the runbook's steps in one transaction: suppress the contact's email_norm (gate._insert_suppression, reason deletion_request) before clearing; clear contacts name, email, email_norm, phone_e164, role, source_url, address and set deleted_at; clear the leads' hypothesis, next_action and property_location (project scope/budget stay for CCGE-032); redact activities; log the removal. The backup stays a manual first step. (3) 'That contact's activities' = activities.contact_id = X or lead_id in the contact's leads. Redaction sets the free-text payload keys note and need to null and replaces every occurrence of the contact's name, email, email_norm and phone inside any payload string with '[removed]'. (4) Mechanism: inside the command's BEGIN IMMEDIATE transaction, drop only the activities_no_update trigger, update payloads, and recreate it from its stored sqlite_master SQL before COMMIT (no migration, so no schema-version change); delete and replace stay blocked. The removal activity is type deletion_request with payload {"reason": "deletion_request", "activities_redacted": N}.

## Plan
1. cottonwood/deletion.py: DeletionError, DeletionResult(line()), delete_contact(conn, contact_id, actor, now).
2. cli.py: deletion-request command following the suppress command's pattern.
3. Spec R-17 exception and R-35 wording; runbook Deletion requests rewritten around the command (keeping the SQL it runs as reference); how-it-works.html wording.
4. tests/test_deletion_request.py covering AC2, the trigger being restored, an unknown contact refused, and other UPDATEs still blocked.

## Acceptance Criteria
- [x] docs/cottonwood-growth-engine.md R-17 states that a deletion request is the one exception under which activity records are changed, and R-35 says the procedure removes the person's details from activity records.
- [x] A test in tests/ shows that after the deletion-request command runs for a contact with a name, email, phone and a note in two activity payloads, no row in contacts or activities contains any of those four values, a new activity records the removal with no personal data in its payload, and the contact's suppression entry is unchanged.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-20.

## Depends on
_None._
