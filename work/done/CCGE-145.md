# CCGE-145 — Untested lead export branches

## Goal
Cover the lead export's deleted or address-less contact, checklist answers, malformed verified_facts, evidence order and organization fields (review 20261115-193520 F-testing-2).

## Inputs
cottonwood/review.py lead_export, _export_contact, _facts, _export_evidence,tests/test_review_lead_export.py

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] Tests in tests/ show that a contact with deleted_at set or an empty email_norm exports draftable false with no_contact_email; that with a checklist configured for direct_candidate an unanswered item exports as unknown; that verified_facts stored as invalid JSON or a non-list exports as []; that evidence is ordered newest observed_at first and includes published_at; and that organization exports its name and domain.

All criteria verified 2026-11-21.

## Depends on
_None._
