# Prospect Review — implementation plan

<!-- Written by /sir:plan. The HOW for spec.md. -->

## Approach
Four small pieces on the existing modules, no new dependency:
1. Config and data: `config.py` gains a typed `ReviewConfig` (checklists per queue, optional max evidence age) read from `review:` in `config/pilot.yaml`; migration 005 adds `leads.checklist`; the research-record schema and `validate.py` accept an optional `checklist` object checked against the configured keys; `prospects.py` stores it and reports it as a difference on re-import.
2. `set-eligibility` in a new `cottonwood/eligibility.py`: load the contact, run every check, refuse with all failures named, else update the contact and append an `eligibility_set` activity.
3. `mark-reviewed` in a new `cottonwood/hand_review.py`: validate lead, result, reviewer and date; refuse a second counted review unless `--replace`, which voids the earlier one with a `correction` row (the same predicate `events.COUNTED_ACTIVITIES_SQL` already honors); the report's existing `hand_review` counting then works unchanged.
4. `review.py` renders the two candidate sections after the inbound section from one query per queue plus newest-evidence and counted-hand-review lookups, sorted in Python by the stated rule.

## Components & changes
- `cottonwood/config.py`: `ChecklistItem(key, label)`, `ReviewConfig(checklists: dict[str, tuple[ChecklistItem, ...]], max_evidence_age_days: int | None)`, `Config.review` with an empty default; `_review(...)` validation raising ConfigError with the key path (`review.checklists.direct_candidate[2].key`).
- `config/pilot.yaml`: `review:` block with both checklists and a commented-out `max_evidence_age_days`.
- `cottonwood/migrations/005_review.sql`: `ALTER TABLE leads ADD COLUMN checklist TEXT` (JSON object text, NULL when absent).
- `cottonwood/schemas/research-record.schema.json`: optional `checklist` object, `additionalProperties` of enum `yes|no|unknown`, property names matching the key pattern.
- `cottonwood/validate.py`: `validate_record(raw, today, checklist_keys)` where `checklist_keys` maps record type to allowed keys; rule `checklist-item` for an unconfigured key; CSV columns `checklist.KEY`; `ProspectRecord.checklist: tuple[tuple[str, str], ...]`.
- `cottonwood/prospects.py`: store `json.dumps(dict(record.checklist), sort_keys=True)` or NULL; `_differences` gains one `checklist.KEY` pair per incoming key.
- `cottonwood/eligibility.py` (new): `EligibilityError(failures: list[tuple[field, rule]])`, `set_eligibility(conn, contact_id, to, source_url, actor, now) -> EligibilityChange`.
- `cottonwood/hand_review.py` (new): `HandReviewError(field, message)`, `mark_reviewed(conn, lead_id, result, reviewer, day, replace, actor, now) -> HandReviewResult`.
- `cottonwood/review.py`: `candidate_rows(conn, lead_type)`, `newest_evidence(conn)`, `counted_hand_reviews(conn)`, `order_candidates(rows)`, `_candidate_section(...)`; `render_review(conn, generated_at, review_config)`.
- `cottonwood/cli.py`: `set-eligibility` and `mark-reviewed` subcommands; `review` and `prospects-import` load the config (existing `--config` option) and pass the review settings.

## Data & interfaces
- Commands:
  - `cottonwood set-eligibility CONTACT {eligible,ineligible,unknown} [--source-url URL] [--actor A] [--db P]` — exit 0 on change or no-op, 1 on refusal (`error: FIELD: RULE` lines, one per failure), unknown contact `error: no contact N`.
  - `cottonwood mark-reviewed LEAD {relevant,irrelevant,fabricated} --reviewer NAME [--date YYYY-MM-DD] [--replace] [--actor A] [--db P]` — exit 0 printing `lead N: hand review RESULT`; 1 on refusal.
- Activities:
  - `eligibility_set`: lead_id NULL, contact_id CONTACT, payload `{"from", "to", "basis"}` with basis `public-source-url` (eligible) or `manual`.
  - `hand_review`: lead_id LEAD, payload `{"result", "reviewer"}`, occurred_at = the start of the Denver date in UTC (the `events._day_start` convention `log-time`/`log-cost` use), recorded_at = now.
  - re-review: `correction` with `voids_activity_id` = the earlier `hand_review` id, payload `{"note": "replaced by mark-reviewed --replace"}`.
- Config:
  ```yaml
  review:
    # max_evidence_age_days: 90
    checklists:
      direct_candidate:
        - {key: direct_signal, label: "Current, directly sourced signal (not just a directory listing)"}
        - ...
  ```
- Review ordering key: `(-yes_count, founder_time is None, founder_time or 0, lead_id)`.
- Evidence age: `(today_denver - date(newest observed_at)).days`; shown `N (over MAX)` when MAX is set and N > MAX.

## Risks & rollback
- Changing `render_review`'s signature touches the CLI and the inbound review tests; keep the inbound section byte-identical so existing assertions hold, and add the config argument with a default.
- `prospects-import` now depends on config: a missing config file must keep working by falling back to the built-in default (no checklist items → every `checklist` key is rejected), and the import test fixtures write their own config where they use checklist answers.
- Schema version moves to 5: the tests pinning 4 are listed in the task's tests_to_change.
- Rollback: revert the branch; migration 005 only adds a nullable column.

## Test strategy
- New test files per task: `tests/test_review_config.py`, `tests/test_prospects_checklist.py`, `tests/test_set_eligibility.py`, `tests/test_mark_reviewed.py`, `tests/test_review_candidates.py`.
- CLI-level tests through `cottonwood.cli.main` with a temp DB and temp config, `timeutil.utc_now` pinned to 2026-12-01T00:00:00Z (Denver date 2026-11-30) as the existing tests do.
- Report integration for hand review via `cottonwood report --from/--to` output lines.
- Each acceptance criterion maps to at least one assertion on exact output lines or stored rows.

## Sequencing
T-01 (config, migration, checklist import) first; T-02 (`set-eligibility`) and T-03 (`mark-reviewed`) are independent of each other and of T-01; T-04 (review queues) needs T-01 and T-03.
