# CCGE-032 — Runbook deletion request clears inbound project scope and budget

## Goal
The deletion-request procedure in docs/runbook.md also clears leads.project_scope and a buyer-stated value_amount/value_basis written by log-inbound, so a deletion request removes everything the inquirer told us (R-35).

## Inputs
docs/runbook.md (Deletion requests, lead free-text step),cottonwood/migrations/003_inbound.sql,work/specs/inbound-logging/assumptions.md (assumption 10)

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [x] The Deletion requests section's lead-clearing step sets project_scope to NULL along with hypothesis, next_action and property_location, and sets value_amount and value_basis to NULL where value_basis is 'buyer-stated'.
- [x] A test extracts that SQL from the runbook, runs it on a migrated database holding a logged inquiry with scope and budget, and asserts those columns are NULL afterwards.

All criteria verified 2026-11-20.

## Depends on
_None._
