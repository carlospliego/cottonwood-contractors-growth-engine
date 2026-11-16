# Approvals And Claims — implementation plan

<!-- Written by /sir:plan. The HOW for spec.md. -->

## Approach
Three commands in a new `cottonwood/gate.py` (architecture: "gate.py — approve, claims, prepare-send, log-outreach, log-reply, suppress"), plus `cottonwood/claims.py` for the claims file, with no migration and no new dependency:
1. `approve SCOPE ITEM`: check approver, reference, date and the scope's item (an existing lead; an existing draft file plus `--lead`; free text for audience and offer), then append one `approval` activity via `events._insert_activity` in a `BEGIN IMMEDIATE` transaction. `approved_on` is a Denver date; `occurred_at` is that day's start (`events._day_start`), `recorded_at` now.
2. Claims: `claims.load_claims(path)` reads `config/claims.yaml` (PyYAML, like `config.load_config`) into frozen `Claim` records and refuses bad entries with `ClaimsError(location, message)`. `approve claim ID` additionally loads the claims file, refuses an unknown or prohibited id or one already verified by an unvoided `claim_verified`, and appends `approval` plus `claim_verified` in the same transaction. `claims.effective_statuses(conn, claims)` computes each claim's effective status and mismatch note; `cottonwood claims` prints them and exits 1 on any mismatch. send-gate reuses `effective_statuses`.
3. `suppress EMAIL --reason TEXT [--source TEXT]`: `normalize.normalize_email`, check exactly one `@` with text on both sides, then `INSERT` into suppression; when the address exists, read the row and report it unchanged. `gate.suppress(conn, email, reason, source, now)` is reused by send-gate's `log-reply opt_out`.

## Components & changes
- `cottonwood/gate.py` (new): `GateError(field, message)` (str `FIELD: MESSAGE`), `SCOPES = ("lead", "draft", "claim", "audience", "offer")`, `Approval` dataclass with `line()`, `approve(conn, scope, item, approver, reference, day, lead_id, actor, now, claims_path)`, `SuppressResult` with `line()`, `suppress(conn, email, reason, source, now)`.
- `cottonwood/claims.py` (new): `STATUSES`, `Claim` (id, text, status, evidence, verified_by, verified_at), `ClaimsError`, `DEFAULT_CLAIMS_PATH = Path("config/claims.yaml")`, `load_claims(path)`, `standing_verification(conn, claim_id)`, `ClaimStatus` (id, status, note), `effective_statuses(conn, claims)`.
- `config/claims.yaml` (new): the five R-19 claims, all `unverified`, with comments explaining that only `approve claim` plus a matching hand edit verifies a claim.
- `cottonwood/cli.py`: `approve`, `claims` and `suppress` Commands.
- Tests: `tests/test_approve.py`, `tests/test_claims.py`, `tests/test_suppress.py`.

## Data & interfaces
- `approval` activity: lead_id (lead and draft scopes, or `--lead`), payload `{scope, item, approver, reference, approved_on}` plus `sha256` for drafts; actor from `--actor` (default `events.DEFAULT_ACTOR`).
- `claim_verified` activity: lead_id NULL, payload `{claim_id, approval_activity_id, verified_by, verified_at}`.
- claims.yaml: `claims:` list of `{id, text, status, evidence, verified_by, verified_at}`; ids match `^[a-z0-9]+(-[a-z0-9]+)*$`.
- stdout: `approval N recorded: SCOPE ITEM by APPROVER` (draft: `... for lead L ...`; claim: `...; mark it verified in config/claims.yaml with verified_by: NAME and verified_at: DATE`); `claims`: `ID: STATUS[ (note)]` per claim; `suppress`: `suppressed EMAIL` or `EMAIL already suppressed since DATE (REASON)`.
- Refusals print `error: FIELD: MESSAGE` and exit 1; argparse usage errors exit 2.

## Risks & rollback
- A founder hand-edits claims.yaml to `verified` without an approval: `effective_statuses` reports it `unverified` with a note, and `claims` exits 1, so send-gate cannot rely on it.
- An approval recorded by mistake: activities are append-only; a `correction` voids it (existing mechanism), and `standing_verification` ignores voided rows.
- Rollback: the feature adds files and three commands and writes only `activities` and `suppression` rows; reverting the merge removes it with no schema change.

## Test strategy
- utc_now pinned to 2026-12-01T00:00:00Z (Denver 2026-11-30), databases in `tmp_path`, claims files written in `tmp_path` and passed with `--claims`.
- One test per AC: printed lines, stored payloads (including the draft SHA-256 computed independently in the test), each refusal's `error: FIELD:` prefix with no activity appended, argparse exit 2, effective statuses and both mismatch notes, the shipped claims file's content, suppression row values and the unchanged existing row, and suppression honored by `prospects-import` and `set-eligibility`.

## Sequencing
T-01 `approve` for lead, draft, audience and offer → T-02 claims file, `claims` command and `approve claim` (needs T-01's approve) → T-03 `suppress`. All three edit `cottonwood/cli.py`, so they run one after another.
