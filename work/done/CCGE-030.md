# CCGE-030 — review command: inbound inquiries with tests labeled and excluded

## Goal
Print or write a Markdown review of inbound inquiries in which test inquiries are labeled TEST and excluded from counts (R-3, R-31 for review).

## Inputs
Spec: `work/specs/inbound-logging/spec.md` (AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-3.5)
Plan: `work/specs/inbound-logging/plan.md`

## Constraints
_None._

## Plan
1. Add cottonwood/review.py: COUNTED_LEADS_FILTER = 'is_test = 0' (documented for report reuse); inbound_rows(conn) joining leads (type inbound_inquiry) to contacts and organizations, newest received_at first then id; inbound_counts(conn) -> totals by channel (form, phone) and segment (commercial, residential, unknown) over non-test rows plus the excluded test count; render_review(conn, generated_at) -> Markdown with '# Review', '## Inbound inquiries', the count line 'Inquiries: N (form a, phone b; commercial c, residential d, unknown e). Test inquiries excluded: M.' and a table with Lead, Received (display_local), Channel, Segment, Stage, Name, Email, Phone, Company, Location, Scope, Budget, Label; NULL prints as '—', '|' is escaped, Label is TEST for tests.
2. Register review in cli.COMMANDS with --out PATH and --db; --out creates parent folders, writes UTF-8, prints 'review written: <path>'; a missing database exits 1 with the error.
3. Add tests/test_review.py.

## Acceptance Criteria
- [x] `cottonwood review` on a database with logged inquiries prints Markdown containing '## Inbound inquiries' and one table row per inbound inquiry, newest received first, showing the lead id, received time as 'YYYY-MM-DD HH:MM -07:00' in America/Denver, channel, segment, stage and the supplied name, email and phone; empty fields print as '—'.
- [x] Rows for inquiries logged with --test contain the label TEST and rows for other inquiries do not.
- [x] With one test form inquiry, one test phone inquiry and one non-test form commercial inquiry, the count line reads 'Inquiries: 1 (form 1, phone 0; commercial 1, residential 0, unknown 0). Test inquiries excluded: 2.'; on an empty migrated database it reads 'Inquiries: 0 (form 0, phone 0; commercial 0, residential 0, unknown 0). Test inquiries excluded: 0.'
- [x] `cottonwood review --out out/review.md` run in a temporary folder creates the missing out folder, writes the same Markdown the command prints without --out, prints the path and exits 0; with a --db path that does not exist it exits 1 with an error message and writes no file.
- [x] A lead whose contact has deleted_at set and name, email and phone NULL is still listed, with '—' in those columns, and review exits 0.
- [x] `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-028
