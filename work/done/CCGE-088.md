# CCGE-088 — Research-record schema, file loading and record validation

## Goal
Turn a JSON or CSV research file into validated prospect records or per-record rejections that name the record, field and rule, with no database access.

## Inputs
Spec: `work/specs/prospect-import/spec.md` (AC-1.3, AC-2.2, AC-2.3)
Plan: `work/specs/prospect-import/plan.md`

## Constraints
_None._

## Plan
1. Add jsonschema>=4.23 to pyproject.toml dependencies and refresh uv.lock (uv add, outside the sandbox).
2. Write cottonwood/schemas/research-record.schema.json (draft 2020-12, additionalProperties false) for the record shape in plan.md Data & interfaces; make sure the package build includes it.
3. cottonwood/validate.py: FileError; RawRecord (number, data); load_records(path) for .json (top-level array) and .csv (header columns from plan.md, empty cell = absent, verified_facts split on newlines, numeric and boolean coercion that leaves bad text for the schema); Rejection(number, record_id, field, rule) with line() -> 'rejected record N[ (ID)]: FIELD: RULE'; ProspectRecord (frozen, normalized values); validate_record(raw, today) mapping the first jsonschema error by path (required reported at the missing key) and then the Python checks: url (http/https with host), date (real YYYY-MM-DD), not-future (after the Denver date today), email and phone through cottonwood.normalize, decimal (plain non-negative digits with optional fraction).
4. tests/test_prospects_validate.py.

## Acceptance Criteria
- [x] cottonwood/schemas/research-record.schema.json loads through importlib.resources from the cottonwood package and passes jsonschema.Draft202012Validator.check_schema; a valid record with type, organization.name, verified_facts, hypothesis and one evidence item with url, observed_at and excerpt validates, and the same record without any one of type, organization.name, verified_facts, hypothesis, evidence, evidence[0].url or evidence[0].observed_at is rejected with rule required at that field; an evidence item with neither excerpt nor observation is rejected.
- [x] validate_record with Denver today 2026-11-30 returns a Rejection whose line() is exactly 'rejected record 2: type: enum' for type 'prospect', 'rejected record 2: evidence: minItems' for an empty evidence list, 'rejected record 2: evidence[0].url: url' for 'ftp://acme.com/x' and for 'https://', 'rejected record 2: evidence[0].observed_at: date' for '2026-02-30', 'rejected record 2: evidence[0].observed_at: not-future' for '2026-12-01', 'rejected record 2: contact.email: email' for 'not-an-email', and 'rejected record 2: contact.phone: phone' for 'call me'; with record_id 'acme-1' the prefix is 'rejected record 2 (acme-1):'; observed_at '2026-11-30' is accepted.
- [x] A value of amount '250000.00' with basis 'founder-estimated' validates and keeps the amount text '250000.00'; an amount without a basis gives 'value.basis: required'; basis 'guess' gives 'value.basis: enum'; amounts '2.5e5', '-1', 'abc' and '1,000' each give 'value.amount: decimal'.
- [x] load_records on a CSV with a header and two data rows returns records numbered 1 and 2 whose data equals the equivalent JSON records (verified_facts split on newlines, empty cells absent); load_records raises FileError naming the path for a .txt file, a missing file, invalid JSON, a JSON object at the top level, and a CSV header without evidence_url.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
