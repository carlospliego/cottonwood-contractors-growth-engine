# CCGE-059 — log-time and log-cost with corrections and totals

## Goal
Record founder (or developer) hours and spend with a date and category, let a wrong entry be voided, and give the report exact totals over an inclusive Denver date range (R-30, R-29 observed vs estimated).

## Inputs
Spec: `work/specs/events-and-stages/spec.md` (AC-5.1, AC-5.2, AC-5.3, AC-5.4, AC-5.5, AC-6.1),Plan: `work/specs/events-and-stages/plan.md`

## Constraints
--voids is also exclusive with --person and --estimated (exit 1, field 'voids'); --note with --voids is the correction's reason (build assumption 17).,time_totals/cost_totals return frozen dataclasses TimeTotals(total, by_person, observed, estimated) and CostTotals(total, by_category, observed, estimated) of Decimal (build assumption 17).,Hours and amounts must be plain decimals (digits with an optional fraction); exponent forms such as '1e1' exit 1 (build assumption 17).,Today in Denver is timeutil.local_date(timeutil.utc_now()), called through the module so tests can pin the clock.

## Plan
In events.py add RawTime/TimeEntry and RawCost/CostEntry with validate_time(raw, today) and validate_cost(raw, today): Decimal parsing (finite, > 0, at most 2 decimal places, hours <= 24), date YYYY-MM-DD not after today's Denver date, category strip+lower non-blank, person in ('founder','developer') default founder, estimated bool, blank note -> None.,log_time/log_cost insert time_logged/cost_logged with lead_id NULL, occurred_at = start of the Denver date in UTC, payload per plan; void_entry(conn, voids_id, kind, actor, now) appends a correction with lead_id NULL after checking type and not already void.,time_totals(conn, start, end) and cost_totals(conn, start, end): counted entries (COUNTED_ACTIVITIES_SQL) whose payload date is within [start, end]; exact Decimal sums: time -> total, by person, observed vs estimated; cost -> total, by category, observed vs estimated; zero when empty.,CLI log-time and log-cost: optional positional amount, --date, --category, --person (time only), --estimated, --note, --voids, --actor, --db; --voids is exclusive with amount/--date/--category and those are required without it (EventError -> exit 1); same connect/error handling as log-event.,Add tests/test_time_cost.py.

## Acceptance Criteria
- [x] `log-time 1.5 --date 2026-11-16 --category Outreach` exits 0 and appends one time_logged activity with lead_id NULL, occurred_at 2026-11-16T07:00:00Z and payload date '2026-11-16', hours '1.5', category 'outreach', person 'founder', estimated false; with --person developer --estimated the payload has person 'developer' and estimated true.
- [x] `log-cost 49.00 --date 2026-11-16 --category "Formspark plan"` exits 0 and appends one cost_logged activity with lead_id NULL and payload amount_usd '49.00', category 'formspark plan', estimated false; --estimated stores estimated true.
- [x] log-time with hours 'abc', '0', '-1', '24.5' or '1.234', log-cost with amount 'abc', '0', '-5' or '1.234', a blank category, a date not in YYYY-MM-DD form, or a date after today in America/Denver each exits 1 and writes no activity.
- [x] `log-time --voids N` on a time_logged entry N and `log-cost --voids M` on a cost_logged entry M each exit 0 and append one correction with lead_id NULL and that voids_activity_id; the wrong entry type, a missing id, an already-void entry, or --voids combined with an amount, --date or --category exits 1 and writes nothing.
- [x] events.time_totals and events.cost_totals over an inclusive Denver date range return exact Decimal sums of counted entries in range (time split by person and observed vs estimated; cost split by category and observed vs estimated), return 0 totals for a range with no entries, and leave out void entries and entries dated outside the range.
- [x] Against a missing database path and an empty (unmigrated) file, log-time and log-cost each exit 1 with stderr starting 'error:' and no 'Traceback', and the empty file still has no tables.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-058
