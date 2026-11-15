# CCGE-081 — Prospecting, outreach, replies, data quality and referrals

## Goal
Show the whole outreach funnel and its failures from the activity types architecture.md names, printing 0 until later features write them: research, hand review per motion, approvals, drafts, sends, gate violations, replies by type, opt-outs, data-quality failures and referred leads per partner (R-28, R-11, R-12).

## Inputs
Spec: `work/specs/weekly-report/spec.md` (AC-4.1, AC-4.2, AC-4.3, AC-4.4, AC-4.5),Plan: `work/specs/weekly-report/plan.md`

## Constraints
Funnel metrics print as - Label: value lines from module constants; per-key labels are Hand review MOTION RESULT, Hand review MOTION total, and Replies TYPE (build assumption 8).,An unknown hand_review result counts only in its motion total; an unknown or missing reply_type counts as other (plan Data & interfaces).,Referrals: a pipe table Partner lead | Name | Referred leads ordered by partner id, cells escaped with review._cell; name = non-blank organization name, else contact name, else the em dash; each referred lead counts once (build assumption 8).

## Plan
In report.py: researched = distinct lead ids of counted imported activities in the period, split by leads.type direct_candidate / relationship_prospect.,Hand review: counted hand_review activities in the period by lead type (motion) and payload result in HAND_REVIEW_RESULTS = (relevant, irrelevant, fabricated); every cell starts at 0.,Approvals, draft_prepared, sent, gate_violation counts.,Replies by payload reply_type over REPLY_TYPES = (interested, not_now, not_relevant, referral, opt_out, bounce, other), unknown or missing -> other; opt-outs = opt_out replies + counted suppressed activities.,Data-quality failures = counted import_rejected + fabricated hand reviews.,Referrals: non-test leads with referred_by not null and a counted imported or inquiry_logged activity in the period, grouped by referred_by with the partner's lead id and organization or contact name ('—' when none), total line.,Render '## Prospecting and outreach', '## Replies and opt-outs', '## Data quality', '## Referrals' sections (pipe tables via review._cell-style escaping).,Tests tests/test_report_funnel.py inserting these activity rows by SQL.

## Acceptance Criteria
- [x] With counted imported activities in the period on two direct_candidate leads (one with two imported activities) and one relationship_prospect lead, plus one on a test lead and one voided, researched direct candidates prints 2 and researched partner firms prints 1; counted hand_review activities with result relevant, irrelevant and fabricated are shown per motion (direct_candidate, relationship_prospect) and result, every combination printing a number, 0 included.
- [x] One counted approval, draft_prepared, sent and gate_violation activity each in the period, plus a voided one of each, print 1 for approvals, prepared drafts, sends and gate violations; an empty database prints 0 for all four.
- [x] Counted reply activities in the period with reply_type interested, not_now, not_relevant, referral, opt_out, bounce and other print 1 each, a reply with an unknown reply_type adds to other, and opt-outs print the opt_out replies plus counted suppressed activities in the period (1 + 1 = 2 for one of each).
- [x] Data-quality failures print the count of counted import_rejected activities in the period plus counted hand_review activities with result fabricated in the period (2 + 1 = 3 for two and one), and 0 on an empty database.
- [x] Two non-test leads with referred_by set to relationship-prospect lead 5 and an inquiry_logged or imported activity in the period are listed under lead 5 with its name and a count of 2, a referred lead whose only such activity is before the period and a referred test lead are not counted, and with no referred leads the total prints 0.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-080
