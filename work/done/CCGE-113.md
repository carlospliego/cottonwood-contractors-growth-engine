# CCGE-113 — No committed sending credentials (R-27) and a runbook section for a research run

## Goal
Fail the suite if an email-sending credential is committed, and write down the research routine from skill run to recorded cost.

## Inputs
Spec: `work/specs/research-skill/spec.md` (AC-4.1, AC-4.2, AC-4.3)
Plan: `work/specs/research-skill/plan.md`

## Constraints
_None._

## Plan
1. tests/test_no_send_credentials.py: a find_credentials(lines) matcher with patterns for assignments (=, :) to names containing SMTP_PASS, SMTP_PASSWORD, SENDGRID_API_KEY, MAILGUN_API_KEY, POSTMARK_SERVER_TOKEN, SES_SECRET, MAIL_PASSWORD with a non-empty value, and smtp:// or smtps:// URLs with user:password@; unit tests per pattern, a comment line and an empty assignment not flagged, .env.example not flagged; a repo test that reads every 'git ls-files' text file (skip undecodable) and asserts no hits, naming file:line.
2. docs/runbook.md: '## Research run' section with numbered steps: start research-prospects with a brief and note the start time; note the end time; prospects-import FILE --check; prospects-import FILE; read /cost; record-run with --cost-source claude-code-cost (or billing-console with --estimated when not exact).
3. tests/test_runbook_research.py checks the section and step order.

## Acceptance Criteria
- [x] A matcher unit test shows each of 'SMTP_PASSWORD=hunter2', 'SENDGRID_API_KEY: SG.abc', 'MAILGUN_API_KEY=key-1', 'POSTMARK_SERVER_TOKEN=x', 'SES_SECRET=y', 'MAIL_PASSWORD=z', 'SMTP_PASS=a' and 'smtp://user:secret@mail.example:587' flagged, and '# SMTP_PASSWORD=', 'SMTP_PASSWORD=' and every line of .env.example not flagged.
- [x] A test reads every file listed by 'git ls-files' that decodes as UTF-8 and asserts the matcher finds nothing, reporting any hit as PATH:LINE; it passes on the repository.
- [x] docs/runbook.md has a '## Research run' section whose numbered steps mention, in this order, 'research-prospects', 'prospects-import' with '--check', 'prospects-import' without --check, '/cost', and 'record-run' with '--cost-source claude-code-cost', and mention 'billing-console' with '--estimated' for a figure that is not exact.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.
- [x] The changes to existing test `tests/test_runbook_inbound.py` keep every behavior it checked at the base commit; they only change what this task's acceptance criteria require (reason given: docs/runbook.md gains the Research run section after Relay; the pinned heading list adds it as the last section).

All criteria verified 2026-11-15.

## Depends on
CCGE-110, CCGE-111
