# CCGE-119 — claims file and claim approvals: a claim is verified only when the file and a founder claim approval agree

## Goal
Ship config/claims.yaml with the five R-19 claims unverified, a loader that refuses malformed claims, 'approve claim ID' that records the approval and a claim_verified activity, and 'cottonwood claims' that prints each claim's effective status and names every mismatch between the file and the recorded approvals (R-19).

## Inputs
Spec: `work/specs/approvals-and-claims/spec.md` (AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5, AC-4.1)
Plan: `work/specs/approvals-and-claims/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/claims.py: STATUSES ('verified','unverified','prohibited'); Claim frozen dataclass; ClaimsError(location, message) with str 'PATH: LOCATION: MESSAGE'; DEFAULT_CLAIMS_PATH = Path('config/claims.yaml'); load_claims(path) with yaml.safe_load, a top-level 'claims' list, and per claim: id lower-kebab-case and unique, text and evidence non-blank, status in STATUSES, verified needs verified_by non-blank and verified_at a YYYY-MM-DD date, unverified/prohibited need both null; standing_verification(conn, claim_id) -> the latest claim_verified activity whose payload claim_id matches and that no correction voids (events._voided_sql), or None; ClaimStatus(id, status, note); effective_statuses(conn, claims) per spec AC-2.4/2.5.
2. config/claims.yaml with the five claims (fashion-place-attribution, service-area, license-classification, insurance-bonding, prior-company-experience), all unverified, evidence naming the open question in docs/cottonwood-growth-engine.md, verified_by/verified_at null, and a header comment on how a claim becomes verified.
3. cottonwood/gate.py: approve scope 'claim' loads the claims file (claims_path argument), refuses ('claim') an unknown id, a prohibited claim, or one with a standing verification, and appends approval and claim_verified in one transaction; the claim line tells the developer what to put in the file.
4. cottonwood/cli.py: approve gains --claims PATH (default claims.DEFAULT_CLAIMS_PATH); new 'claims' Command with --claims and --db that prints 'ID: STATUS' or 'ID: STATUS (NOTE)' per claim and exits 1 on any note; a ClaimsError prints 'error: ...' and exits 1.
5. tests/test_claims.py: shipped file content, every loader refusal, approve claim payloads and refusals, effective statuses for agreeing, verified-without-approval, approved-but-unverified and voided cases.

## Acceptance Criteria
- [x] config/claims.yaml loads with claims.load_claims and lists exactly five claims with ids fashion-place-attribution, service-area, license-classification, insurance-bonding and prior-company-experience, each with non-empty text, status 'unverified', non-empty evidence, and verified_by and verified_at null.
- [x] 'cottonwood claims --claims FILE' exits 1 and prints a stderr line starting 'error:' that names FILE, the claim (its index or id) and the field, for each of these files: a claim with no id; two claims with the same id; an id 'Service_Area'; blank text; blank evidence; status 'maybe'; a verified claim with no verified_by; a verified claim with verified_at '30/11/2026'; an unverified claim with verified_by set; a prohibited claim with verified_at set.
- [x] With utc_now pinned to 2026-12-01T00:00:00Z, 'cottonwood approve claim service-area --approver Founder --reference "email 2026-11-30 Re: claims" --claims FILE' exits 0, prints 'approval N recorded: claim service-area by Founder; mark it verified in config/claims.yaml with verified_by: Founder and verified_at: 2026-11-30', and appends an 'approval' activity (scope 'claim', item 'service-area') and a 'claim_verified' activity whose payload has claim_id 'service-area', approval_activity_id equal to the approval's id, verified_by 'Founder' and verified_at '2026-11-30'. 'approve claim' exits 1 with a stderr line starting 'error: claim:' and appends nothing for an id not in FILE, for a prohibited claim, and for a claim that already has a claim_verified activity no correction voids.
- [x] 'cottonwood claims --claims FILE' prints one line per claim in file order, 'ID: STATUS', and exits 0 when they agree: a claim marked verified with verified_by Founder and verified_at 2026-11-30 and a matching claim_verified activity prints 'ID: verified'; a prohibited claim prints 'ID: prohibited'; an unverified claim with no approval prints 'ID: unverified'.
- [x] 'cottonwood claims --claims FILE' exits 1 when a claim is marked verified with no matching unvoided claim_verified activity (also when verified_by or verified_at differ, or the activity is voided by a correction), printing 'ID: unverified (marked verified but no matching claim approval)', and when a claim has a claim_verified activity but the file says unverified, printing 'ID: unverified (approved on 2026-11-30 by Founder; mark it verified in the claims file)'. Without --claims it reads config/claims.yaml.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-118
