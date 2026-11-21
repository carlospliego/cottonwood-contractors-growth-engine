# Events And Stages — plan

<!-- Written by /sir:plan. HOW the spec gets built. -->

## Approach
**Context:**
- `cottonwood/cli.py:15-33`: exit codes 0/1/2, a `Command` dataclass, and one `_add_*_arguments`/`_run_*` pair per command, registered in `COMMANDS` (`cottonwood/cli.py:248`).
- `cottonwood/cli.py:158-203`: `_run_log_inbound` is the pattern to follow. It validates before opening the DB, catches `db.MigrationError` from `db.connect` and `sqlite3.Error` around the writes, and closes in `finally`.
- `cottonwood/inbound.py:187`: `log_inquiry` does its inserts in one transaction and calls `conn.rollback()` on any error. Its `_rowid` helper is at `cottonwood/inbound.py:155`. `inbound.DEFAULT_ACTOR` is `developer`.
- `cottonwood/timeutil.py:30`: `parse_received` takes Denver local or UTC Z input, and `to_utc_iso`/`utc_now` produce stored values. `local_date` and `display_local` are there too, with `DENVER` as the zone.
- `cottonwood/migrations/002_core.sql`:
  - `leads.stage` has a CHECK per type (lines 38-57);
  - `activities` has `voids_activity_id` and append-only triggers (lines 76-106);
  - JSON payloads are checked by `json_valid`.
- `cottonwood/review.py:16`: `COUNTED_LEADS_FILTER` (`is_test = 0`) is the only counting rule so far.
- `db.connect` does not check the schema version. An unmigrated file fails at the first query with `sqlite3.OperationalError` (inbound-logging assumption 7).

**Approach:**
- Add one module, `cottonwood/events.py`, with pure validation (raw CLI values → frozen dataclasses), write functions that run in one transaction, and read helpers (`counted_activities`, `time_totals`, `cost_totals`).
- The CLI gets three commands: `log-event`, `log-time` and `log-cost`.
- `log-event` with `--stage` updates `leads.stage` in place and appends `stage_change`. The lead's history lives in the append-only activities.
- Corrections append a `correction` row with `voids_activity_id`. When the voided event caused the lead's latest effective stage change, the stage is reverted with a new `stage_change` that names the correction.
- The counting rule is one SQL fragment, so weekly-report reuses it rather than re-deriving it.
- There is no migration.

## Components & changes
| Component | Change | Story |
|---|---|---|
| `cottonwood/events.py` | new. Holds:<br>• the constants `EVENT_TYPES` (R-15), `DIRECT_STAGES` and `RELATIONSHIP_STAGES` (R-14), and `STAGES_BY_LEAD_TYPE`;<br>• `EventError(field, message)`;<br>• `RawEvent`/`Event` with `validate_event(raw, now)`;<br>• `log_event(conn, event)`, returning `(event_id, stage_change_id or None, from_stage)`;<br>• `log_correction(conn, lead_id, voids_id, at, note, actor)`;<br>• `RawTime`/`TimeEntry` and `RawCost`/`CostEntry` with their validators, plus `log_time`, `log_cost` and `void_entry(conn, voids_id, kind, actor, now)`;<br>• `COUNTED_ACTIVITIES_SQL`, `counted_activities(conn, type=None)`, `time_totals` and `cost_totals` | US-1–US-6 |
| `cottonwood/cli.py` | `log-event`, `log-time` and `log-cost` commands. Each validates, then connects, then writes, and maps errors to exit codes. | US-1, US-5, US-6 |
| `tests/test_events.py` | event types, `--at`, unknown lead, note, output line | US-1, US-6 |
| `tests/test_events_stages.py` | R-14 stages per lead type, stage_change payload, refusals | US-2 |
| `tests/test_events_qualify.py` | R-16 need and procurement URL rules | US-3 |
| `tests/test_events_corrections.py` | voids, stage revert, refusals, counted_activities, test leads | US-4 |
| `tests/test_time_cost.py` | log-time, log-cost, `--voids`, totals | US-5, US-6 |

## Data & interfaces
- **Event payload:**
  - `{"event": <type>, "note"?: str, "need"?: str, "procurement_url"?: str}`
  - Keys are present only when given.
- **stage_change payload:**
  - `{"from": <stage>, "to": <stage>, "event_activity_id": <id>}`
  - lead_id is the lead, and occurred_at is the event's time.
- **correction:**
  - type `correction`, `voids_activity_id` = the target, payload `{"note"?: str}`;
  - for a lead event, lead_id is the lead;
  - for a time or cost entry, lead_id is NULL.
- **time_logged:**
  - lead_id NULL, occurred_at = `to_utc_iso(datetime(date, 00:00, DENVER))`;
  - payload `{"date": "YYYY-MM-DD", "hours": "<Decimal str>", "category": str, "person": "founder"|"developer", "estimated": bool, "note"?: str}`.
- **cost_logged:**
  - same shape, with `"amount_usd": "<Decimal str>"` in place of hours and no person.
- **Effective stage change:**
  - a `stage_change` row that no correction voids, whose `event_activity_id` names an activity that no correction voids;
  - the latest one is chosen by (occurred_at, id) descending;
  - `log-event --stage` with an `--at` earlier than the lead's latest effective stage change (reverts aside) is refused with exit 1 and writes nothing, so `leads.stage` always equals that latest change and a correction reverts to the right stage (CCGE-060). The same time is allowed: the new change ranks after it by id.
- **Counted activities:**

  ```sql
  a.type <> 'correction'
  AND NOT EXISTS (SELECT 1 FROM activities c WHERE c.type = 'correction' AND c.voids_activity_id = a.id)
  AND NOT (a.type = 'stage_change' AND EXISTS (SELECT 1 FROM activities c WHERE c.type = 'correction'
           AND c.voids_activity_id = json_extract(a.payload, '$.event_activity_id')))
  AND (a.lead_id IS NULL OR EXISTS (SELECT 1 FROM leads l WHERE l.id = a.lead_id AND l.is_test = 0))
  ```

- **CLI:**
  - `log-event LEAD_ID TYPE --at T [--stage S] [--note N] [--need N] [--procurement-url U] [--voids ID] [--actor A] [--db P]`
    - TYPE choices are `EVENT_TYPES + ('correction',)`.
  - `log-time [HOURS] [--date D] [--category C] [--person founder|developer] [--estimated] [--note N] [--voids ID] [--actor A] [--db P]`
  - `log-cost [AMOUNT] [--date D] [--category C] [--estimated] [--note N] [--voids ID] [--actor A] [--db P]`
  - For log-time and log-cost, the positional argument, `--date` and `--category` are required unless `--voids` is given, in which case they are forbidden. This is checked in validation, which exits 1.
- **Exit codes:** 0 on success; 1 on validation, refusal or database errors, with `error: ...` on stderr; 2 for argparse usage errors.

## Risks & rollback
- **Stage revert ordering:** two events logged with the same occurred_at are ordered by activity id. Tests cover reverting the newest and refusing to revert an older one.
- **Payload free text and R-35:** recorded as an open question, not solved here. The help text warns against putting contact details in notes.
- **Partial writes:** each command uses one transaction with rollback on any exception. A test uses a trigger to make the second insert fail and checks that nothing remains.
- **Rollback:** the change is code only, with no migration. Reverting the PR removes the commands. Rows already written stay valid activities of unknown type to the old code.

## Test strategy
- AC-1.1–1.4: `tests/test_events.py`:
  - parametrized over every R-15 type, through `cli.main([...])` on a migrated tmp DB with an inbound lead from `log-inbound`;
  - asserts the rows via sqlite3 and the stdout line;
  - "later than now" uses a year-2999 `--at`.
- AC-2.1–2.3: `tests/test_events_stages.py`:
  - parametrized over every stage per lead type;
  - direct and relationship leads are inserted directly with SQL;
  - refusals assert the count of activities is unchanged and the stage is unchanged.
- AC-3.1–3.3: `tests/test_events_qualify.py`.
- AC-4.1–4.5: `tests/test_events_corrections.py`:
  - checks the voided row is byte-identical before and after;
  - checks the contents of `counted_activities`;
  - covers a revert and a refused revert;
  - covers each refusal case and a test lead.
- AC-5.1–5.5: `tests/test_time_cost.py`:
  - CLI writes, refusals, and `--voids` (including the wrong kind);
  - totals over ranges with void and out-of-range entries;
  - Decimal equality.
- AC-6.1: a missing DB and an empty (unmigrated) file, for each command.
- AC-6.2: a trigger raising on a `stage_change` insert, then asserting no activities and an unchanged stage.
- Command: `uv run pytest`, plus `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .`.

## Sequencing
1. T-01: `events.py` core, and `log-event` for the R-15 types (US-1, AC-6.1 for log-event).
2. T-02: stages and R-16. Adds `--stage`, `--need` and `--procurement-url`, the stage_change activity and rollback (US-2, US-3, AC-6.2). Depends on T-01.
3. T-03: corrections and the counted-activity rule (US-4). Depends on T-02.
4. T-04: `log-time`, `log-cost`, `--voids` and the totals (US-5, AC-6.1 for these). Depends on T-03, for `COUNTED_ACTIVITIES_SQL` and the correction row shape.
