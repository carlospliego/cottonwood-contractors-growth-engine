# CCGE-130 — Sending config and the draft claims list contract

## Goal
Let the pilot config hold the sender identity, postal address, opt-out line and ad identification every sendable draft must carry, shipped unset, and define and validate the claims list that accompanies a draft (R-21).

## Inputs
Spec: `work/specs/send-gate/spec.md` (AC-1.1, AC-1.2, AC-5.1)
Plan: `work/specs/send-gate/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/config.py: SendingConfig frozen dataclass (sender_identity, postal_address, opt_out_line, ad_identification: str, default ''); _sending(value, path) accepting None/missing as empty, refusing a non-mapping section ('sending must be a mapping') and a non-string value ('sending.KEY must be a string'); Config.sending with a default factory; values stripped.
2. config/pilot.yaml: a commented 'sending:' section describing each key and that prepare-send refuses while sender_identity or postal_address is empty.
3. cottonwood/schemas/draft-claims.schema.json: draft 2020-12, type array, items object with required claim_id (string, pattern ^[a-z0-9]+(-[a-z0-9]+)*$) and status (enum verified/unverified/prohibited), additionalProperties false.
4. cottonwood/draft_claims.py: DraftClaimsError(path, message) str 'PATH: MESSAGE'; load_draft_claims(path) -> tuple of claim ids, refusing a missing file, invalid JSON and schema errors (first error's path and message).
5. tests/test_sending_config.py and tests/test_draft_claims.py.

## Acceptance Criteria
- [x] config.load_config on a file with 'sending: {sender_identity: "Cottonwood Contractors", postal_address: "1 Main St, Sandy, UT 84070", opt_out_line: "Reply STOP to opt out.", ad_identification: "Advertisement"}' returns config.sending with those four values; a file with no sending section, or with only some keys, loads the missing ones as ''.
- [x] config.load_config raises ConfigError whose message contains 'sending' for 'sending: [1]' and contains 'sending.postal_address' for 'sending: {postal_address: 12}'; config/pilot.yaml still loads, has a 'sending' section only in comments, and load_config of it returns four empty sending values.
- [x] cottonwood/schemas/draft-claims.schema.json exists; draft_claims.load_draft_claims returns ('service-area', 'licensed') for a file holding [{"claim_id": "service-area", "status": "verified"}, {"claim_id": "licensed", "status": "unverified"}] and returns () for [].
- [x] draft_claims.load_draft_claims raises DraftClaimsError whose message names the file for each of: a missing file, '{not json', '{}' (not an array), [{"claim_id": "Service_Area", "status": "verified"}], [{"claim_id": "a", "status": "maybe"}], [{"claim_id": "a"}] and [{"claim_id": "a", "status": "verified", "extra": 1}].
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
_None._
