# Send Gate — implementation plan

<!-- Written by /sir:plan. The HOW for spec.md. -->

## Approach
Four pieces on top of `cottonwood/gate.py`, `cottonwood/claims.py` and `cottonwood/eligibility.py`, with no migration and no new dependency:
1. Config and contract: `config.SendingConfig` (four strings, empty by default) parsed from an optional `sending:` mapping like `review:`; `cottonwood/schemas/draft-claims.schema.json` plus `draft_claims.load_draft_claims(path)` using `jsonschema.Draft202012Validator` like `validate.schema()`.
2. `prepare-send LEAD DRAFT [--claims PATH] [--claims-file PATH] [--out DIR]`: gather every failure (never stop at the first) in a fixed order: approval, eligibility, suppression, claims, evidence, sender_identity, postal_address, opt_out, ad_identification. All pass: copy the draft bytes to `OUT/NAME` and append `draft_prepared` in one transaction (file written after the insert succeeds, inside the transaction, and removed if the commit fails). Any fail: append `prepare_refused` with the check names and write nothing.
3. `log-outreach LEAD [--prepared N] --recipient EMAIL --source-url URL --message FILE --sender NAME [--date] [--provider-message-id]`: validate inputs (refuse with `error: FIELD:`), compute violation reasons against the prepared activity, append `sent`, and append `gate_violation` when any reason applies, in one transaction.
4. `log-reply LEAD TYPE [--date] [--note]`: append `reply`; for `opt_out` insert into suppression (reuse a transaction-free helper extracted from `gate.suppress`) and append `suppressed`; for `bounce` call `eligibility._apply(... 'ineligible' ...)` inside the same transaction.

## Components & changes
- `cottonwood/config.py`: `SendingConfig` dataclass and `_sending()` parser; `Config.sending`.
- `config/pilot.yaml`: a commented `sending:` section explaining each key.
- `cottonwood/schemas/draft-claims.schema.json` (new) and `cottonwood/draft_claims.py` (new): `DraftClaimsError`, `load_draft_claims(path) -> tuple[str, ...]` (the claim ids).
- `cottonwood/send.py` (new): `prepare_send`, `log_outreach`, `log_reply`, their result dataclasses with `line()`s, `Refusal(check, detail)`, `SendError(field, message)`.
- `cottonwood/gate.py`: `_insert_suppression(conn, email_norm, reason, source, now)` shared by `suppress` and `log-reply`.
- `cottonwood/cli.py`: `prepare-send`, `log-outreach`, `log-reply` Commands.
- Tests: `tests/test_sending_config.py`, `tests/test_draft_claims.py`, `tests/test_prepare_send.py`, `tests/test_log_outreach.py`, `tests/test_log_reply.py`.

## Data & interfaces
- `draft_prepared` payload: `{draft, sha256, sendable, claim_ids, lead_approval_id, draft_approval_id}`; lead_id and contact_id set.
- `prepare_refused` payload: `{draft, checks: [names]}`.
- `sent` payload: `{prepared, source_url, message, message_sha256, sender, sent_on, provider_message_id, recipient_matches}`; `gate_violation` payload: `{sent_activity_id, reasons}`.
- `reply` payload: `{type, received_on, note}`; `suppressed` payload: `{source: "log-reply"}`.
- Claims list default path: the draft path with `.md` replaced by `.claims.json` (`--claims-file` overrides); claims library default `config/claims.yaml` (`--claims`).
- Evidence freshness: the lead's newest `evidence.observed_at` (a date) is no older than `review.max_evidence_age_days` days before today in America/Denver.

## Risks & rollback
- A partly written sendable file: the copy happens only after every check passes and inside the transaction; on any exception the file is removed and the transaction rolled back.
- A gate check silently skipped: each refusal reason has its own test, and a test with every check failing asserts the full ordered list.
- Rollback: new commands and files only, writing `activities`, `suppression` and `contacts.eligibility`; reverting the merge removes them with no schema change.

## Test strategy
- utc_now pinned to 2026-12-01T00:00:00Z (Denver 2026-11-30); a `_ready_lead` fixture builds the all-checks-pass state (config with all four sending values and max age 30, eligible contact, evidence 2026-11-20, lead and draft approvals via `cottonwood approve`, a claims library with a verified claim backed by `approve claim`).
- One test per refusal check, one with every check failing, the sendable file's bytes, payloads, `log-outreach` clean and each violation reason, `log-reply` for every type, opt-out and bounce side effects and their refusals.

## Sequencing
T-01 sending config and draft-claims contract → T-02 `prepare-send` → T-03 `log-outreach` → T-04 `log-reply`. T-02..T-04 all edit `cottonwood/cli.py` and `cottonwood/send.py`, so they run one after another.
