# Weekly Report — implementation plan

<!-- Written by /sir:plan from spec.md. Every decision traces to a story or constraint. -->

## Approach
Add `cottonwood/report.py`, a read-only module that builds the R-28 report in two steps: first `build_report(conn, period, settings, generated_at) -> Report`, which computes a frozen dataclass of every metric, then `render_report(report) -> str`, which turns it into Markdown. Tests can then check numbers on the dataclass and the layout on the text separately. Every activity metric is one query over `activities a WHERE {events.COUNTED_ACTIVITIES_SQL} AND a.type = ?`, plus a period filter on the Denver date of `a.occurred_at` (cottonwood/events.py:316). Corrections, voids, void-caused stage changes, correction reverts and test leads therefore drop out under the one R-17 rule (spec Constraints). Founder hours and other costs reuse `events.time_totals` / `events.cost_totals` (cottonwood/events.py:737, :753). Inbound counts copy `review.inbound_counts`: every channel and segment key starts at 0 (cottonwood/review.py:62), filtered by `review.COUNTED_LEADS_FILTER` and by `received_at` in the period.

The period filter is applied in Python, not SQL. A row's UTC timestamp is converted with `timeutil.local_date` (cottonwood/timeutil.py:68) and kept when `start <= d <= end`. That avoids hand-written DST offsets in SQL and makes the AC-1.2 boundary (06:59:59Z vs 07:00:00Z in MST) exact. Volumes are a pilot's (tens to hundreds of rows), so fetching typed rows and filtering in Python is cheap.

A new `report` command in `cottonwood/cli.py` follows `review`'s conventions (cottonwood/cli.py:206-248):
- `--out` creates parent directories and prints `report written: PATH`;
- `--db` selects the database;
- a `db.MigrationError` or `sqlite3.Error` exits 1 with `error:`.

It adds:
- `--period {7d,30d}`, `--from`, `--to`;
- `--config`, as `backup` has (cottonwood/cli.py:71).

The period is parsed and validated before the database is opened, so a bad period never touches the file (AC-1.3).

`config.Config` gains two optional fields, read from a `report:` mapping in config/pilot.yaml:
- `model_cost_cap_usd: Decimal | None`;
- `sending_blocked_by: str | None`.

Bad values raise `ConfigError`, which the command turns into exit 1. The report never writes to the database.

## Components & changes
| Area / file | Change | Serves |
|---|---|---|
| `cottonwood/report.py` (new) | `Period` (start, end dates) and `parse_period(period, from_, to, today) -> Period` raising `ReportError`; `working_day`, `ack_target_met`; metric helpers (`_counted_in_period`, `_inbound`, `_acknowledgements`, `_conversations`, `_prospecting`, `_outreach`, `_replies`, `_referrals`, `_model_cost`); frozen `Report`; `build_report`; `render_report` | US-1–US-5 |
| `cottonwood/cli.py` | `report` subcommand: `--period`, `--from`, `--to`, `--out`, `--db`, `--config`; `_run_report` with review's error and output handling | US-1 |
| `cottonwood/config.py` | `Config.model_cost_cap_usd`, `Config.sending_blocked_by`; parse the optional `report:` mapping (cap: a non-negative decimal number or string; blocked: string, blank means None) | AC-5.1, AC-5.3 |
| `config/pilot.yaml` | Commented `report:` block documenting both keys (left unset) | AC-5.1, AC-5.3 |
| `tests/test_report_period.py`, `tests/test_report_inbound.py`, `tests/test_report_conversations.py`, `tests/test_report_funnel.py`, `tests/test_report_costs.py` (new) | Tests per story; activities inserted by SQL for the types later features own | all |
| `docs/runbook.md` (if present) | One "weekly report" step: `cottonwood report --period 7d --out out/report.md` | US-1 |

## Data & interfaces
- **CLI:** `cottonwood report (--period 7d|30d | --from YYYY-MM-DD --to YYYY-MM-DD) [--out PATH] [--db PATH] [--config PATH]`.
  - Exit 0 on success.
  - Exit 1 with `error: …` on stderr for a bad period, a config error, a missing or unmigrated database, a read error or a write error.
  - `--period` uses argparse `choices`, so a value outside the list exits 2 as argparse does elsewhere. AC-1.3 lists combinations, half pairs, the missing form, bad date text and from > to; those are all checked in `parse_period` and exit 1.
- **Period:** "today" is `events.denver_today()`, which reads the pinned `timeutil.utc_now`.
  - 7d = [today-6, today].
  - 30d = [today-29, today].
  - The header line is `Period: YYYY-MM-DD to YYYY-MM-DD (America/Denver)`.
- **Membership:**
  - activities: `timeutil.local_date(occurred_at)` falls in the period;
  - inquiries: `local_date(leads.received_at)`;
  - time and cost: payload `date`, through the totals functions;
  - agent runs: `local_date(started_at)`.
- **Acknowledgement target:** for each non-test inbound lead received in the period:
  - `ack` = the earliest counted `acknowledgement` on that lead, by (occurred_at, id), at any time, even after the period;
  - `r` = the Denver date of `received_at`;
  - working days are Monday–Friday;
  - if `r` is a working day the deadline is `r`; otherwise it is the next working day after `r`;
  - the result is within target when `local_date(ack.occurred_at) <= deadline`, outside target when it is later, and not acknowledged when there is no `ack`.
- **Qualified:** `count(DISTINCT a.lead_id)` over counted `stage_change` rows in the period where `json_extract(a.payload,'$.to') = events.QUALIFIED_STAGE`. COUNTED_ACTIVITIES_SQL already removes void-caused changes and reverts (AC-3.1, AC-5.4).
- **KPI:** `(qualified + partner_conversations) / founder.total`, using Decimal division quantized with ROUND_HALF_UP to `0.01`. It prints `n/a` when `founder.total == 0`.
- **Founder hours:** `time_totals` returns observed and estimated across all persons, not per person. So `report.py` computes founder observed/estimated itself from the same counted `time_logged` entries filtered by `person == 'founder'`. It cross-checks that their sum equals `time_totals(...).by_person.get('founder', 0)`, which is enforced in a test. Developer hours come from `by_person['developer']`.
- **Payload contract for later features** (assumption 4):
  - `hand_review.result` ∈ {relevant, irrelevant, fabricated};
  - `reply.reply_type` ∈ {interested, not_now, not_relevant, referral, opt_out, bounce, other}.

  A value outside those sets is counted under `other` for replies, and left out of a hand-review bucket but kept in that motion's total.
- **Researched counts:** distinct leads of type `direct_candidate` or `relationship_prospect` with `is_test = 0` (enforced by COUNTED_ACTIVITIES_SQL's lead join) and a counted `imported` activity in the period.
- **Referrals:** non-test leads with `referred_by IS NOT NULL` whose counted `imported` or `inquiry_logged` activity is in the period. They are grouped by `referred_by`, and each partner is named by its lead id and organization or contact name (`—` when it has none).
- **Model cost:**
  - sum `Decimal(cost_usd)` over `agent_runs` rows with a non-null `cost_usd` started in the period, split by `cost_estimated` (1 = estimated);
  - month-to-date covers the same rows whose `started_at` Denver date falls between the 1st of the end date's month and the end date;
  - against a cap the report prints `MTD of CAP` and the remaining amount, or `No model-cost cap configured (report.model_cost_cap_usd).`
- **Blocked sending:** when `sending_blocked_by` is non-blank the report prints a `## Sending blocked` section quoting the text; otherwise there is no such section and the word "blocked" does not appear.
- **Markdown layout:**
  - `# Weekly report`, then `Generated: <display_local>` and the period line;
  - sections: `## Inbound`, `## Conversations and KPI`, `## Hours`, `## Prospecting and outreach`, `## Replies and opt-outs`, `## Data quality`, `## Referrals`, `## Costs`, and `## Sending blocked` when set;
  - each metric is one `- Label: value` line or a pipe table with every key listed, zeros included;
  - money prints with 2 decimals.
- **No migrations.** No schema change; config gains keys only.

## Risks & rollback
| Risk | Mitigation | Rollback |
|---|---|---|
| Later features write payload keys other than `result` / `reply_type` | The spec and assumptions record the keys as a contract; tests pin them; the later feature's plan cites this plan | Change the key constant in report.py |
| DST edge on period boundaries | Membership via `timeutil.local_date` in Python, tested at the 06:59:59Z / 07:00:00Z MST boundary and a summer (MDT) boundary | — |
| Double counting when both an event and its stage_change exist | Outcomes count events; only qualified uses stage_change (assumption 3) | — |
| A bad config value stops the report | `ConfigError` gives exit 1 with the key named; the keys are optional and absent by default | Remove the key from pilot.yaml |
| A heavy query on a large DB | Pilot volumes only; queries are per type with the counted filter | — |
| Report output holds contact data (partner names) | Written under git-ignored `out/` by convention, as review is | — |

Rollback for the whole feature: revert the PR. Nothing persistent changes (no migration, no database writes).

## Test strategy
All tests are pytest (`UV_OFFLINE=1 UV_NO_SYNC=1 uv run pytest`). Each test builds a migrated temp DB and inserts leads and activities by SQL, or through `events.log_event` / `log_time` / `log_cost` where those exist. `timeutil.utc_now` stays pinned to 2026-12-01T00:00:00Z by the autouse fixture, so Denver today = 2026-11-30. CLI tests call `cli.main([...])` with `capsys`.

| AC | Test |
|---|---|
| AC-1.1 | `parse_period('7d', today=2026-11-30)` → 11-24..11-30; `30d` → 11-01..11-30; the CLI header line contains `2026-11-24 to 2026-11-30 (America/Denver)` |
| AC-1.2 | `--from 2026-11-01 --to 2026-11-15` with `missed_call` events at 2026-11-16T06:59:59Z (counted) and 2026-11-16T07:00:00Z (not counted); the count line shows 1 |
| AC-1.3 | Parametrized: period+from, period+to, from only, to only, none, `2026-1-5`, `2026-02-30`, from > to; each exits 1, stderr starts `error:`, and `--out` is not created |
| AC-1.4 | stdout mode exits 0 and starts with `# Weekly report`; `--out tmp/a/b/r.md` creates dirs, the file matches the stdout text, and `report written:` is printed; missing DB and empty file each exit 1 with no `Traceback` |
| AC-2.1 | form/phone × segments plus a test inquiry; a lead received before the period is excluded; every key prints, zeros included |
| AC-2.2 | Fixed dates (2026-11-27 is a Friday, 11-28 Saturday, 11-30 Monday): working day acknowledged same day → within; acknowledged the next day → outside; Saturday acknowledged Monday → within; Saturday acknowledged Tuesday → outside; a voided acknowledgement only → not acknowledged; the earliest of two decides |
| AC-2.3 | Counted vs voided `missed_call` / `call_returned` |
| AC-3.1 | Two moves into buyer_need_confirmed on one lead → 1; a voided move → 0; a correction revert does not add; a test lead → 0 |
| AC-3.2 | One of each event type plus a voided one → 1 each |
| AC-3.3 | Founder observed 2 + estimated 1, developer 3 → founder total 3, observed 2, estimated 1, developer 3 on its own line |
| AC-3.4 | qualified 1 + partner 1 over 3 hours → `0.67`; 0 hours → `n/a` |
| AC-4.1–4.5 | SQL-inserted `imported`, `hand_review`, `approval`, `draft_prepared`, `sent`, `gate_violation`, `reply`, `suppressed`, `import_rejected` rows, with void and test-lead cases, and `referred_by` leads; an empty DB prints every label with 0 |
| AC-5.1 | `agent_runs` rows inside and outside the period and month; estimated split; config with cap `100` → `MTD … of 100.00`; no `report:` key → no-cap sentence |
| AC-5.2 | Two categories, estimated and observed, matched to `cost_totals` |
| AC-5.3 | Config with `sending_blocked_by: "Q3: sender domain"` → section quotes it; blank or absent → no `Sending blocked` text |
| AC-5.4 | Leads with only `inquiry_logged`, `imported` or `note` → qualified 0 |

Checks: `uv run pytest`, `uv run ruff check .`, `uv run mypy .`, `uv run ruff format --check .`.

## Sequencing
1. **T-01:** period parsing, the CLI command, config plumbing, the report skeleton and US-2 (inbound, acknowledgements, calls). It establishes `report.py`, `build_report` / `render_report` and the CLI, which everything else extends.
2. **T-02:** US-3 (qualified, partner and outcomes, hours, KPI) and AC-5.4. These depend on T-01's skeleton.
3. **T-03:** US-4 (prospecting, outreach, replies, data quality, referrals). This depends on T-01.
4. **T-04:** US-5 cost parts (model cost against the cap, other costs, blocked sending), including the config keys. This depends on T-01.

T-02, T-03 and T-04 touch the same files (report.py and its renderer), so they run in sequence (T-02 → T-03 → T-04) to avoid merge conflicts.
