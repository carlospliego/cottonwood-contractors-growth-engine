# Events And Stages — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
Once an inquiry or prospect is in the database (inbound-logging, data-core), nothing records what happens next: the acknowledgement, calls, missed and returned calls, remote screens, walkthroughs, proposals, wins and losses, partner conversations, or where the lead stands. Founder hours and spend are not recorded either. Without these, the phase-3 report (weekly-report) has nothing honest to count, and the month-one KPI, (qualified direct conversations + partner conversations) ÷ founder hours (docs/cottonwood-growth-engine.md:14, R-28), cannot be computed.

The developer needs to log each event with its time and move the lead's stage only to values R-14 allows. A lead may count as a qualified conversation (`buyer_need_confirmed`) only on stated evidence (R-16). Mistakes must be corrected without editing history (R-17), and hours and costs must be logged with a date and category (R-30).

This is solved when every R-15 event type can be logged, a stage outside R-14 or an unevidenced qualification is refused, and a voided activity drops out of the counted activities and the time and cost totals that the report reads.

## Goals / non-goals
- Goal: `cottonwood log-event <lead-id> <type>` records every R-15 event type with its time, and moves the lead's stage when asked, recording the change as an activity that names the event (R-14, R-15).
- Goal: a lead enters `buyer_need_confirmed` only through an event stating a confirmed need or a procurement URL (R-16).
- Goal: `log-event <lead-id> correction --voids <activity-id>` voids an earlier event. A void activity is left out of every count this feature defines (R-17).
- Goal: `cottonwood log-time` and `cottonwood log-cost` record founder hours and spend with a date and category. Totals for a date range are available to the report (R-30).
- Non-goal: the `report` command and its R-28/R-29 metrics, including the same-working-day acknowledgement target. These belong to weekly-report.
- Non-goal: creating direct-candidate or relationship-prospect leads (`prospects-import`, phase 4). Replies and sends (`log-reply`, `log-outreach`, phase 5). Model cost of skill runs (`record-run`, phase 4).
- Non-goal: checking that a procurement URL is reachable or active. Voiding `inquiry_logged` or other non-event activities.

## User stories
### US-1 — Log an event on a lead
As the developer, I want to record what happened on a lead and when, so that the report counts real activity.

Acceptance criteria:
- AC-1.1: For each of `acknowledgement`, `call`, `missed_call`, `call_returned`, `remote_screen`, `walkthrough`, `proposal`, `won`, `lost`, `partner_conversation`, `handoff` and `note` (the last with `--note`), `cottonwood log-event <lead-id> <type> --at "2026-11-16 09:30"` exits 0. It appends exactly one activity of that type for the lead, with occurred_at `2026-11-16T16:30:00Z`, the given or default actor, and a recorded_at. The lead's stage is unchanged.
- AC-1.2: `--at` accepts a UTC timestamp ending in Z (`2026-11-16T16:30:00Z` stores the same value). A missing `--at`, an unparseable `--at`, or a time later than now exits 1 and writes nothing. A type outside the R-15 list exits 2 and writes nothing.
- AC-1.3: A lead id that does not exist exits 1 with `error: no lead <id>` and writes nothing. `note` without `--note` (or with blank text) exits 1 and writes nothing. `--note` text on any other type is stored in the event payload.
- AC-1.4: The success line names the activity id, the type, the lead id and the America/Denver time.

### US-2 — Move a lead's stage within R-14
As the developer, I want an event to move the lead to its new stage, so that the lead record shows where it stands, with the move explained by an event.

Acceptance criteria:
- AC-2.1: `log-event <inbound-lead> call --at ... --stage contacted_or_replied` sets the lead's stage to `contacted_or_replied`. It appends the `call` activity and one `stage_change` activity whose payload holds `from` `candidate`, `to` `contacted_or_replied` and `event_activity_id` (the call activity's id). Both activities share the same occurred_at, and the success line shows `stage candidate -> contacted_or_replied`.
- AC-2.2: Every stage in R-14's direct/inbound list is accepted for `inbound_inquiry` and `direct_candidate` leads. Every stage in the relationship list is accepted for `relationship_prospect` leads. Any order of moves is allowed.
- AC-2.3: A stage outside the lead type's list (for example `introduced` on an inbound lead, `walkthrough` on a relationship prospect, or `bogus`), or the lead's current stage, exits 1 with a message listing that type's allowed stages. It writes no activity and leaves the stage unchanged.

### US-3 — Qualify only on stated evidence
As the founder, I want a lead to count as a qualified conversation only when a confirmed need or an active procurement is recorded, so that the KPI is not inflated.

Acceptance criteria:
- AC-3.1: `--stage buyer_need_confirmed` with `--need "needs 4,000 sq ft office TI by March"` succeeds, and the event payload stores that need text. With `--procurement-url https://bids.example.gov/rfp/123` it succeeds and the payload stores the URL.
- AC-3.2: `--stage buyer_need_confirmed` without `--need` or `--procurement-url`, with blank `--need`, or with a procurement URL that is not an absolute http(s) URL, exits 1. It writes nothing and the stage stays unchanged.
- AC-3.3: `--need` or `--procurement-url` without `--stage buyer_need_confirmed` exits 1 and writes nothing.

### US-4 — Correct a mistaken event
As the developer, I want to void a mistaken event without editing history, so that counts drop it while the audit trail keeps it.

Acceptance criteria:
- AC-4.1: `log-event <lead> correction --voids <event-id> --at ...` exits 0 and appends one `correction` activity whose voids_activity_id is that event's id. The voided activity row is unchanged.
- AC-4.2: The voided event, the correction itself and any stage_change the voided event caused do not appear in `events.counted_activities(conn)`. The lead's other non-void events do appear.
- AC-4.3: Voiding the event behind the lead's latest effective stage change returns the lead to that change's `from` stage. It appends a `stage_change` whose `event_activity_id` is the correction's id. If a later effective stage change exists, the correction exits 1 naming that later change and writes nothing.
- AC-4.4: A correction exits 1 and writes nothing in each of these cases:
  - `--voids` is missing;
  - the activity does not exist;
  - the activity belongs to another lead;
  - the activity is not an R-15 event (`stage_change`, `correction`, `inquiry_logged`);
  - the activity is already void;
  - `--stage` is given.
- AC-4.5: Activities on test leads (is_test 1) are not counted by `events.counted_activities`.

### US-5 — Record founder hours and spend
As the developer, I want to record the founder's hours and spend with a date and category, so that the report can total them and compute the KPI.

Acceptance criteria:
- AC-5.1: `cottonwood log-time 1.5 --date 2026-11-16 --category Outreach` exits 0. It appends one `time_logged` activity with no lead, occurred_at `2026-11-16T07:00:00Z` (start of that Denver day), and payload with date `2026-11-16`, hours `1.5`, category `outreach`, person `founder` and estimated false. `--person developer` and `--estimated` are stored.
- AC-5.2: `cottonwood log-cost 49.00 --date 2026-11-16 --category "Formspark plan"` exits 0. It appends one `cost_logged` activity with no lead and payload with amount_usd `49.00`, category `formspark plan` and estimated false. `--estimated` is stored.
- AC-5.3: Hours that are not a decimal, ≤ 0, > 24 or have more than 2 decimal places exit 1 and write nothing. The same applies to an amount that is not a decimal, ≤ 0 or has more than 2 decimal places, a blank category, a date not in `YYYY-MM-DD` form, or a date after today in America/Denver.
- AC-5.4: `log-time --voids <id>` voids a `time_logged` entry and `log-cost --voids <id>` voids a `cost_logged` entry, each by appending a `correction` with no lead. The wrong entry type, a missing id, an already-void entry, or `--voids` combined with an amount, `--date` or `--category` exits 1 and writes nothing.
- AC-5.5: `events.time_totals(conn, start, end)` and `events.cost_totals(conn, start, end)` (inclusive America/Denver dates) return exact Decimal sums of the counted entries in the range. Time totals split by person and observed vs estimated; cost totals split by category and observed vs estimated. A range with no entries totals 0. Void entries and entries outside the range are left out.

### US-6 — Safe failures
As the developer, I want failures to leave the database unchanged and explain themselves, so that a refused command never half-writes.

Acceptance criteria:
- AC-6.1: For log-event, log-time and log-cost, a missing database file or an unmigrated database exits 1 with a line starting `error:`, prints no traceback and creates no tables.
- AC-6.2: If an insert fails partway through log-event (the event is written but the stage_change is not), the transaction is rolled back: no activity is written and the lead's stage is unchanged.

## Constraints & assumptions
- Times are stored in UTC and shown in America/Denver (R-32). Input formats match `log-inbound --received` (`cottonwood/timeutil.py:30`).
- Activities stay append-only: the existing triggers (`cottonwood/migrations/002_core.sql:88`) reject UPDATE and DELETE, so corrections are new rows (R-17).
- No new migration or table: events, time and cost are `activities` rows (architecture decision 9).
- Every question the brief left open took its recommended answer under /sir:yolo. The 13 answers are in `work/specs/events-and-stages/assumptions.md`:
  - scope split with weekly-report;
  - the log-event interface and its required `--at` (future times refused);
  - stage storage and validation, with no transition order;
  - event types allowed on every lead type;
  - R-16 enforcement via `--need`/`--procurement-url`;
  - free text kept in payloads;
  - correction targets and stage revert;
  - the counted-activity rule;
  - the log-time and log-cost interfaces (free-text categories, person, estimated);
  - `--voids` for time and cost entries;
  - the totals helpers;
  - output and failure messages.

## Success metrics
- Every R-15 type and every R-14 stage is covered by a passing test. Every refusal named in US-2 to US-6 has a test showing that nothing was written.
- weekly-report can compute the KPI from `counted_activities`, `time_totals` and `cost_totals` without re-deriving the void or test rules.

## Open questions
- **For the founder (R-35 vs R-17):** event notes and need statements are free text inside append-only activity payloads, so a deletion request cannot clear them. This is the same conflict as data-core assumption 8.
- **For the founder:** R-16's "accessible active procurement" is attested by the developer giving the URL; the tool does not check it.
- **For weekly-report:** should hours logged by `--person developer` show in the report? This feature keeps them out of founder hours.
