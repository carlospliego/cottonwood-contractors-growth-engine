# Prospect Import — implementation plan

<!-- Written by /sir:plan. HOW we will satisfy spec.md. -->

## Approach
**Context (Phase 0):**
- Schema: `leads` has type, organization_id, contact_id, stage (CHECK per type), property_location, hypothesis, next_action, founder_time_h, value_amount/value_basis (TEXT), referred_by, is_test, received_at (cottonwood/migrations/002_core.sql:36-63); `evidence` has lead_id, url, observed_at, published_at, excerpt, kind (`fact`/`hypothesis`), source_status (002_core.sql:67-75); `organizations.domain_norm` is unique where not null (002_core.sql:13-14); `suppression.email_norm` is the key (002_core.sql:124-129). There is no column for verified facts or an observation.
- Migrations are numbered SQL files applied by the runner (cottonwood/migrations/003_inbound.sql adds a column the same way).
- Normalization exists: `normalize_email`, `normalize_phone` (E.164), `normalize_domain` (strips scheme and `www.`), `normalize_name` (cottonwood/normalize.py:14-65); each raises ValueError on bad input.
- Write conventions: `inbound.log_inquiry` inserts organization/contact/lead/activity in one transaction, keeps personal data out of payloads (R-35) and reuses organizations by `name_norm` (cottonwood/inbound.py:140-152, 187-250); `_rowid` checks `lastrowid` (inbound.py:155-159).
- The report already counts `imported` activities as researched leads per motion and `import_rejected` as data-quality failures, through `events.COUNTED_ACTIVITIES_SQL` (cottonwood/report.py:298-335); referrals count leads with `referred_by` that have an `imported` activity in the period (report.py:348-370).
- CLI style: argparse subcommand per command, `--db` default from `$COTTONWOOD_DB`, `--actor` default `inbound.DEFAULT_ACTOR`, exit 0/1/2 (cottonwood/cli.py:110-175).
- `pyproject.toml` depends on pyyaml and tzdata only; architecture.md decision 4 chooses jsonschema.

**Approach:** a pure validation module turns a file into validated records or per-record rejections; an import module matches and writes each record inside its own savepoint; the CLI prints one line per record and a summary. Validation never touches the database except the `referred_by` lookup, which runs at import time.

## Components & changes
| Area / file | Change | Serves |
|---|---|---|
| `pyproject.toml`, `uv.lock` | Add `jsonschema>=4.23` | US-1 |
| `cottonwood/schemas/research-record.schema.json` (new) | Draft 2020-12 schema for one record; packaged with the module | AC-1.3, US-2 |
| `cottonwood/validate.py` (new) | `load_records(path) -> list[RawRecord]` (JSON array or CSV rows → record dicts; `FileError` on file-level problems); `validate_record(raw, number, today) -> ProspectRecord | Rejection` (schema errors mapped to `FIELD: RULE`, plus date, URL, email, phone, decimal checks); `Rejection(number, record_id, field, rule)` with `line()` | US-1, US-2 |
| `cottonwood/migrations/004_prospects.sql` (new) | `ALTER TABLE leads ADD COLUMN verified_facts TEXT`; `ALTER TABLE evidence ADD COLUMN observation TEXT` | AC-1.1, AC-1.2 |
| `cottonwood/prospects.py` (new) | `import_records(conn, file_name, outcomes, actor) -> ImportResult`: per record a savepoint; referrer check; org/contact/lead/evidence matching; inserts; `imported` / `import_rejected` activities; differing-field list; suppression → `ineligible` | US-2–US-4 |
| `cottonwood/cli.py` | `prospects-import FILE [--db] [--actor]`; prints `created lead N (TYPE)` / `matched lead N (+K evidence)` per record and diff lines on stdout, `rejected …` lines on stderr, then `imported I, matched M, rejected R`; exit 1 if R > 0 or on a file error | US-1, US-2 |
| `tests/test_prospects_validate.py`, `tests/test_prospects_import.py`, `tests/test_prospects_reimport.py` (new) | Tests per story with synthetic, labeled fixtures | all |

## Data & interfaces
**JSON record** (top level: an array):
```
{"record_id": "acme-1",                       optional, shown in messages
 "type": "direct_candidate" | "relationship_prospect",
 "organization": {"name": "...", "domain": "acme.com", "type": "...", "category": "..."},
 "contact": {"name": "...", "email": "...", "phone": "...", "role": "...", "source_url": "https://..."},   optional; name or email required when present
 "property_location": "...", "verified_facts": ["..."], "hypothesis": "...",
 "next_action": "...", "founder_time_h": 0.5,
 "value": {"amount": "250000.00", "basis": "buyer-stated" | "founder-estimated" | "unverified"},
 "referred_by": 12, "is_test": false,
 "evidence": [{"url": "https://...", "observed_at": "2026-11-20", "published_at": "2026-11-01",
               "excerpt": "...", "observation": "...", "kind": "fact" | "hypothesis"}]}   excerpt or observation required; kind defaults to fact
```
Unknown keys are rejected (`additionalProperties: false`) so a typo is not silently dropped.

**CSV columns:** `record_id, type, organization_name, organization_domain, organization_type, organization_category, contact_name, contact_email, contact_phone, contact_role, contact_source_url, property_location, verified_facts, hypothesis, next_action, founder_time_h, value_amount, value_basis, referred_by, is_test, evidence_url, evidence_observed_at, evidence_published_at, evidence_excerpt, evidence_observation, evidence_kind`. Required header columns: `type, organization_name, verified_facts, hypothesis, evidence_url, evidence_observed_at`, and one of `evidence_excerpt` / `evidence_observation`. Empty cell = key absent, except an empty `hypothesis` cell is `""` and an empty `verified_facts` cell is `[]`, as a JSON record may carry them (CCGE-091); `verified_facts` split on newlines (blank lines dropped); `founder_time_h` / `referred_by` parsed as numbers and `is_test` from `true/false/1/0`, otherwise left as text so the schema reports `type`. The record number is the data row number (1 = first row after the header).

**Messages:** `rejected record N[ (RECORD_ID)]: FIELD: RULE` where FIELD is a JSON path (`evidence[0].url`, `value.basis`, `organization.name`) and RULE the jsonschema keyword (`required`, `type`, `enum`, `minItems`, `minLength`, `additionalProperties`, `anyOf`) or one of `url`, `date`, `not-future`, `email`, `phone`, `decimal`, `referrer`. A missing key is reported at its own path (`evidence[0].url: required`, not the parent). Only the first error per record is printed, ordered by path, so output is deterministic.

**Activities:** `imported` (lead_id, contact_id; payload `{file, record, record_id, created, new_evidence}`), `import_rejected` (no lead; payload `{file, record, record_id, field, rule}`); `occurred_at` = `recorded_at` = now; actor from `--actor`.

**Stored values:** stage `researched`; `verified_facts` JSON array text; value_amount the decimal text as given (validated plain decimal); evidence `observed_at`/`published_at` as `YYYY-MM-DD`; contact `email_norm`, `phone_e164` normalized; organization `name_norm`, `domain_norm` normalized; eligibility `ineligible` when `email_norm` is suppressed, else `unknown`.

**Diff fields** (matched rows, incoming non-empty and different): `organization.name`, `organization.domain`, `organization.type`, `organization.category`, `contact.name`, `contact.phone`, `contact.role`, `contact.source_url`, `hypothesis`, `verified_facts`, `next_action`, `founder_time_h`, `value.amount`, `value.basis`, `referred_by`, `is_test`.

## Risks & rollback
| Risk | Mitigation | Rollback |
|---|---|---|
| Adding jsonschema needs PyPI access during `uv sync` | Run `uv add` outside the sandbox once; the lock file pins it | Remove the dependency and the schema check |
| jsonschema error paths differ from the documented `FIELD: RULE` | Map `error.absolute_path` and, for `required`, append the missing key; tests pin each AC-2.2 message | — |
| A partial record written on failure | One SAVEPOINT per record, released on success and rolled back on any error | — |
| Personal data in append-only payloads | Payloads limited to file name, numbers, ids, field and rule; a test asserts no excerpt/name/email text | — |
| Matching on name merges distinct firms with the same name | Domain wins when present; name matching only without a domain (R-7) | — |
| The schema is not found when installed | Shipped inside the package and loaded with `importlib.resources`; a test loads it by that path | — |

## Test strategy
Commands: `uv run pytest`, `uv run ruff check .`, `uv run mypy .`, `uv run ruff format --check .`.
| AC | Test |
|---|---|
| AC-1.1 | JSON fixture of 2 records → exit 0; leads (type, stage researched), organizations, evidence rows and one counted `imported` activity per lead; stdout last line |
| AC-1.2 | Same two records as CSV → the stored rows (excluding ids) equal the JSON import's |
| AC-1.3 | `Draft202012Validator.check_schema` on the packaged schema; removing each required key from a valid record makes `validate_record` reject it |
| AC-1.4 | Parametrized: `.txt`, missing file, `{` , `{}`, CSV without `evidence_url`; exit 1, stderr `error:` and the path, every table count unchanged |
| AC-2.1 | 3-record file with record 2 missing `evidence[0].url` (with and without record_id); stderr line; counts; exit 1 |
| AC-2.2 | Parametrized over each invalid case; the rejection line matches exactly; Denver today 2026-11-30 (utc_now pinned to 2026-12-01T00:00:00Z), so `2026-12-01` is not-future and `2026-11-30` passes |
| AC-2.3 | Valid value stored as text; each bad value case rejected with the exact line |
| AC-2.4 | The `import_rejected` payload keys and no record text; `report --from/--to` shows `Data-quality failures: 1` |
| AC-3.1 | Import twice; second summary; all five table counts equal |
| AC-3.2 | Pre-insert an org with domain_norm acme.com; domain match under another name; name match without domain; new domain creates an org |
| AC-3.3 | Contact by email; by name in the same org without email; a deleted contact does not match; lead key with property location `" 12 Main St "` vs `"12 main st"` and both empty |
| AC-3.4 | Re-import with one extra evidence item and a changed category: one evidence row and one activity added, stored values unchanged, the diff line printed |
| AC-3.5 | Same lead twice in one file → created then matched; summary |
| AC-4.1 | Suppressed email → `ineligible`; others `unknown`; no `eligible` row after any import |
| AC-4.2 | Referrer exists and is relationship → stored; missing id and a direct lead id → `referred_by: referrer` |
| AC-4.3 | `is_test: true` → is_test 1 and the report's researched lines stay 0 |
| AC-4.4 | One direct + one relationship → report lines 1 and 1 |

## Sequencing
1. T-01 Record schema, file loading and validation (US-1 loading/schema, US-2) — no database.
2. T-02 `prospects-import` writes new records, rejections, suppression, referrals, test labels, report integration (US-1 import, US-2 activity, US-4).
3. T-03 Re-import matching, evidence dedupe and differing-field output (US-3).
