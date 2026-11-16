# CCGE-111 — prospects-import --check: validate a research file exactly as the import would, writing nothing

## Goal
Let the developer validate a skill output file with the import's loader, schema, rules and checklist keys and see the same rejection lines, without writing to the database, so the run's validation result can be recorded before import (R-25).

## Inputs
Spec: `work/specs/research-skill/spec.md` (AC-2.1, AC-2.2, AC-4.3)
Plan: `work/specs/research-skill/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/cli.py: prospects-import gains --check (store_true). In _run_prospects_import, after loading the config and records and validating each record (unchanged code), when args.check: print each Rejection.line() to stderr, print 'check: N valid, M rejected' to stdout, return EXIT_REFUSED if M else EXIT_OK, without connecting to the database.
2. tests/test_prospects_check.py: one valid + one invalid JSON record (stderr line equal to the import's rejection line, counts of leads/evidence/organizations/contacts/activities unchanged, no import_rejected activity), all valid, unreadable/invalid JSON file, and a checklist key not configured rejected under --check with --config.

## Acceptance Criteria
- [x] For a JSON file whose record 1 is valid and record 2 lacks evidence, 'cottonwood prospects-import FILE --check' exits 1, prints on stderr exactly the 'rejected record 2' line that 'cottonwood prospects-import FILE' prints for the same file, prints 'check: 1 valid, 1 rejected' on stdout, and the row counts of leads, evidence, organizations, contacts and activities are the same before and after (no import_rejected activity).
- [x] For a file with two valid records, --check exits 0, prints 'check: 2 valid, 0 rejected', and creates no lead; for a file that is not valid JSON, --check exits 1 with the same stderr 'error:' line the import prints; with --config naming a config whose direct_candidate checklist lacks key 'direct_signal', a record answering checklist.direct_signal is rejected under --check with 'checklist.direct_signal: checklist-item'.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
