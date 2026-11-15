# CCGE-080 — Conversations, outcomes, hours and the month-one KPI

## Goal
Show qualified direct conversations, partner conversations, remote screens, walkthroughs, proposals, wins, founder and developer hours, and the KPI (qualified + partner) / founder hours, counting qualification only from a counted stage change into buyer_need_confirmed (R-28, R-16, R-29).

## Inputs
Spec: `work/specs/weekly-report/spec.md` (AC-3.1, AC-3.2, AC-3.3, AC-3.4, AC-5.4),Plan: `work/specs/weekly-report/plan.md`

## Constraints
Labels (build assumption 7): Qualified direct conversations, Partner conversations, Remote screens, Walkthroughs, Proposals, Won projects, KPI (qualified + partner) per founder hour under ## Conversations and KPI; Founder hours, Founder hours observed, Founder hours estimated, Developer hours under ## Hours.,Hours print as str() of the exact Decimal sum; the KPI is quantized to 0.01 ROUND_HALF_UP and prints n/a at 0 founder hours (build assumption 7).,The founder observed/estimated split is summed from events._entries_in_range (the entries time_totals reads) filtered to person founder, cross-checked against time_totals.by_person in a test (build assumption 7).

## Plan
In report.py: qualified = len({row.lead_id}) over _counted_in_period(conn, 'stage_change', period) whose payload 'to' equals events.QUALIFIED_STAGE.,Outcome counts for partner_conversation, remote_screen, walkthrough, proposal, won via _counted_in_period.,Hours: founder total/observed/estimated from counted time_logged entries in the period's dates with person founder (reuse events.time_totals for totals and by_person; compute the founder split from the same entries); developer = by_person developer or 0.,KPI = Decimal(qualified + partner) / founder_total quantized to 0.01 ROUND_HALF_UP; 'n/a' when founder_total is 0.,Render '## Conversations and KPI' and '## Hours' sections with '- Label: value' lines.,Tests tests/test_report_conversations.py.

## Acceptance Criteria
- [x] A non-test lead with two counted stage changes into buyer_need_confirmed in the period adds 1 to qualified direct conversations; a move into buyer_need_confirmed that a correction voided adds 0; a correction's stage revert adds 0; a test lead's move adds 0; a move dated before the period adds 0.
- [x] With one counted event each of partner_conversation, remote_screen, walkthrough, proposal and won in the period plus a voided one of each, the report shows 1 for each of the five; on an empty database each prints 0.
- [x] With founder entries of 2 observed hours and 1 estimated hour and a developer entry of 3 hours dated in the period, plus a founder entry dated after the period, the report shows founder hours total 3, observed 2, estimated 1, and developer hours 3 on a separate line.
- [x] With 1 qualified direct conversation, 1 partner conversation and 3 founder hours the KPI prints 0.67; with founder hours 0 it prints n/a.
- [x] A non-test lead whose only activities are inquiry_logged, imported and note activities in the period adds 0 to qualified direct conversations.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-079
