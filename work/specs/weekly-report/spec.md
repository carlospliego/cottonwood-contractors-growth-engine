# Weekly Report — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
The founder has 5–10 sales hours a week and no record of what the pilot actually produced: inquiries may be lost, and outreach, replies, conversations, hours and spend live in the developer's head. Each week the developer needs one Markdown report covering a period that shows every R-28 metric, zeros included, observed figures apart from estimates (R-29), and the month-one KPI: (qualified direct conversations + partner conversations) ÷ founder hours (docs/cottonwood-growth-engine.md:14, :64). It is solved when `cottonwood report --period 7d` and `--period 30d` write that file from the database alone, and every number in it can be traced to counted rows.

## Goals / non-goals
- Goal: `cottonwood report` for `--period 7d|30d` or inclusive `--from`/`--to` America/Denver dates, written to stdout or a file (R-28, R-31).
- Goal: every R-28 metric appears, printed as 0 when there is nothing to count, built on the one counted-activity rule (`events.COUNTED_ACTIVITIES_SQL`), with test leads excluded (R-3, R-17).
- Goal: observed apart from estimated for founder hours, other costs and model cost (R-29); the KPI is shown as `n/a` when founder hours are 0.
- Goal: metrics whose rows later features write (prospect-import, prospect-review, approvals-and-claims, send-gate, research-skill) are read from the activity types and tables architecture.md names, so they report 0 today and real counts once those features land, with no report change.
- Non-goal: CSV output (docs/cottonwood-growth-engine.md:103), charts, emailing the report, or any command that writes the activities later features own.
- Non-goal: enforcing the model-cost cap; caps are record-only (docs/cottonwood-growth-engine.md:82).

## User stories
### US-1 — Choose the period and where the report goes
As the developer, I want to run `cottonwood report` for the last 7 or 30 days or for given dates, and print it or write it to a file, so that I can send the founder the same report every week.

Acceptance criteria:
- AC-1.1: With "today" in America/Denver being D, `report --period 7d` covers the Denver dates D-6 to D inclusive and `--period 30d` covers D-29 to D inclusive; the report header states the period as `YYYY-MM-DD to YYYY-MM-DD (America/Denver)`.
- AC-1.2: `report --from 2026-11-01 --to 2026-11-15` covers those Denver dates inclusive; an activity that occurred at 2026-11-16T06:59:59Z (23:59:59 MST on 2026-11-15) is counted and one at 2026-11-16T07:00:00Z is not.
- AC-1.3: `--period` together with `--from`/`--to`, `--from` without `--to` (or the reverse), neither form, a date not in YYYY-MM-DD form, or `--from` later than `--to` each exits 1 with stderr starting `error:` and writes no file.
- AC-1.4: Without `--out` the Markdown goes to stdout and the command exits 0; with `--out PATH` it creates missing parent directories, writes the file, prints `report written: PATH` and exits 0; a missing or unmigrated database exits 1 with stderr starting `error:` and no `Traceback`.

### US-2 — Inbound handling metrics
As the founder, I want to see inquiries by channel and segment, how many were acknowledged within the same-working-day target, and missed and returned calls, so that I can tell whether inquiries are being lost.

Acceptance criteria:
- AC-2.1: The report lists inbound inquiries received in the period by channel and by segment, with a total; test inquiries (`is_test` 1) are not counted, and a channel or segment with no inquiries prints 0.
- AC-2.2: For each non-test inquiry received in the period, the earliest counted `acknowledgement` event decides the target: within target when received on a working day (Monday–Friday, America/Denver) and acknowledged on the same Denver date, or received on a non-working day and acknowledged by the end of the next working day; otherwise outside target; with no counted acknowledgement it counts as not acknowledged. The three counts print, zeros included.
- AC-2.3: The report counts counted `missed_call` and `call_returned` events that occurred in the period.

### US-3 — Conversations, outcomes and the KPI
As the founder, I want qualified direct conversations, partner conversations, remote screens, walkthroughs, proposals, wins, founder hours and the KPI, so that I can judge whether sales time is turning into conversations.

Acceptance criteria:
- AC-3.1: Qualified direct conversations are the number of distinct non-test leads with a counted `stage_change` into `buyer_need_confirmed` that occurred in the period; a voided move and a correction's stage revert do not count.
- AC-3.2: Partner conversations, remote screens, walkthroughs, proposals and won projects are the counts of counted `partner_conversation`, `remote_screen`, `walkthrough`, `proposal` and `won` events that occurred in the period.
- AC-3.3: Founder hours are `events.time_totals` for the period's dates, person `founder`, shown as total, observed and estimated; developer hours are shown on a separate line and are not founder hours.
- AC-3.4: The KPI is (qualified direct conversations + partner conversations) ÷ total founder hours, printed with 2 decimal places, and printed as `n/a` when founder hours are 0.

### US-4 — Prospecting, outreach and data quality
As the founder, I want research, review, approval, draft, send, gate-violation, reply, opt-out, referral and data-quality counts, so that I see the whole outreach funnel and its failures, even while those parts are not yet in use.

Acceptance criteria:
- AC-4.1: Researched direct candidates and partner firms are the distinct non-test `direct_candidate` and `relationship_prospect` leads with a counted `imported` activity in the period; hand-review counts are counted `hand_review` activities in the period by lead type (motion) and payload `result` (`relevant`, `irrelevant`, `fabricated`), zeros printed.
- AC-4.2: Approvals, prepared drafts, sends and gate violations are the counts of counted `approval`, `draft_prepared`, `sent` and `gate_violation` activities in the period.
- AC-4.3: Replies are counted `reply` activities in the period, by payload `reply_type` for each of `interested`, `not_now`, `not_relevant`, `referral`, `opt_out`, `bounce` and `other`, zeros printed; opt-outs are replies with `reply_type` `opt_out` plus counted `suppressed` activities in the period.
- AC-4.4: Data-quality failures are counted `import_rejected` activities in the period plus counted `hand_review` activities with `result` `fabricated` in the period.
- AC-4.5: Referred leads are non-test leads with a non-null `referred_by` whose counted `imported` or `inquiry_logged` activity is in the period, listed per referring partner (lead id and name), with a total that prints 0 when there are none.

### US-5 — Costs against the cap, estimates and blockers
As the founder, I want model cost against the monthly cap, other costs, observed apart from estimated, and any open question that blocks sending, so that I can see spend and what is holding outreach up.

Acceptance criteria:
- AC-5.1: Model cost is the sum of `agent_runs.cost_usd` for runs started in the period, as an exact decimal, split into observed and estimated by `cost_estimated`; the report also shows month-to-date model cost for the America/Denver calendar month containing the period's end date against `report.model_cost_cap_usd` from config/pilot.yaml, or states that no cap is configured.
- AC-5.2: Other costs are `events.cost_totals` for the period's dates, shown as total, observed and estimated and by category.
- AC-5.3: When config/pilot.yaml sets `report.sending_blocked_by` to non-blank text, the report states that sending is blocked and quotes that text; otherwise it contains no blocked-sending statement.
- AC-5.4: The report never counts a lead as qualified from anything but a counted `stage_change` into `buyer_need_confirmed`; a lead whose only record is an `inquiry_logged`, `imported` or `note` activity adds 0 to qualified direct conversations.

## Constraints & assumptions
- Every activity metric uses `events.COUNTED_ACTIVITIES_SQL` (cottonwood/events.py), which drops corrections, voided rows, stage changes whose cause is void, correction reverts and test leads; lead counts also filter `is_test = 0` (R-3).
- An activity is in the period when its `occurred_at`, converted to America/Denver, falls on a date in the period; time and cost entries use their payload `date`; agent runs use `started_at` (build assumption).
- The working-day rule for the acknowledgement target (Monday–Friday, America/Denver, no holidays) is a build assumption; the spec gives the target but no working days (docs/cottonwood-growth-engine.md:20).
- Payload keys `result` (hand_review), `reply_type` (reply) are set here as the contract later features write; architecture.md names the activity types but no payload keys.
- `report.model_cost_cap_usd` and `report.sending_blocked_by` are new optional keys in config/pilot.yaml; an absent key means no cap configured and nothing blocked.
- The report is Markdown in the same style as `review` (title, generated time in Denver, `##` sections, pipe tables); it reads the database and never writes to it.

## Success metrics
- The developer produces the weekly report with one command and sends the file; the 30-day report shows every R-28 metric with zeros printed (project outcome, docs/cottonwood-growth-engine.md:12).

## Open questions
- [Founder] The monthly model-cost cap amount (docs/cottonwood-growth-engine.md:135); until it is set the report says no cap is configured.
- [Founder] Whether the same-working-day target should observe Utah holidays or business hours; this build uses Monday–Friday whole days.
- [Founder] Whether the KPI should use observed founder hours only; this build divides by total founder hours (observed + estimated) and shows both.
