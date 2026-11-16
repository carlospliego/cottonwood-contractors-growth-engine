# CCGE-131 — prepare-send: write a sendable draft only when every R-21 check passes

## Goal
Make prepare-send the only producer of a sendable draft: copy the approved draft to out/send only when the lead and draft approvals, eligibility, suppression, claims, evidence age and the configured sender identity, postal address, opt-out line and ad identification all check out, and otherwise refuse naming every failed check (R-21).

## Inputs
Spec: `work/specs/send-gate/spec.md` (AC-2.1, AC-2.2, AC-2.3, AC-5.1)
Plan: `work/specs/send-gate/plan.md`

## Constraints
_None._

## Plan
1. cottonwood/send.py (new): CHECKS order ('approval','eligibility','suppression','claims','evidence','sender_identity','postal_address','opt_out','ad_identification'); Refusal(check, detail) with line() 'refused: CHECK: detail'; SendError(field, message); PrepareResult(activity_id, sendable) with line(); prepare_send(conn, lead_id, draft, out_dir, claims_path, claims_list_path, settings, today, actor, now) -> PrepareResult or raises PrepareRefused(refusals, activity_id). Checks: latest unvoided approval scope lead for the lead; latest unvoided approval scope draft for the lead whose sha256 equals the draft file's; lead contact exists with an email, eligibility 'eligible'; contact email_norm not in suppression; draft_claims.load_draft_claims, claims.load_claims, and every id effectively verified per claims.effective_statuses (unknown id, unverified or prohibited fail); newest evidence observed_at within review.max_evidence_age_days of today (unset, none, or older fail); draft text contains sending.sender_identity, postal_address, opt_out_line and (if set) ad_identification, an empty sender_identity/postal_address failing as 'not configured'. Pass: in BEGIN IMMEDIATE insert draft_prepared (lead_id, contact_id) then write OUT/NAME bytes, removing it if commit fails. Fail: insert prepare_refused {draft, checks}.
2. cottonwood/cli.py: prepare-send Command (lead int, draft path, --claims default config/claims.yaml, --claims-file default DRAFT with .md -> .claims.json, --out default out/send, --actor, --db, --config); unknown lead -> 'error: lead:'.
3. tests/test_prepare_send.py with a _ready fixture and one test per check plus all-fail ordering.

## Acceptance Criteria
- [x] With utc_now pinned to 2026-12-01T00:00:00Z and every R-21 condition met (all four sending values configured, review.max_evidence_age_days 30, lead 1's contact eligible and unsuppressed, evidence observed 2026-11-20, unvoided lead approval and draft approval with matching sha256 recorded with cottonwood approve, the draft containing the four configured values, and a claims list whose one claim is verified by the claims file and a matching approve claim), 'cottonwood prepare-send 1 DRAFT --claims CLAIMS --out OUT' exits 0, writes OUT/NAME byte-identical to DRAFT (NAME the draft's file name), prints 'sendable draft written: OUT/NAME (prepared N)', and appends one draft_prepared activity with lead_id 1, the contact's id, and payload keys draft, sha256, sendable, claim_ids, lead_approval_id and draft_approval_id.
- [x] Each single failure makes prepare-send exit 1, leave OUT without NAME, print a stderr line starting 'refused: CHECK:' and append one prepare_refused activity whose payload checks list is [CHECK]: no lead approval and a draft approval whose sha256 differs (approval); contact ineligible (eligibility); contact address suppressed (suppression); claims list missing, and a claim not in the claims file, unverified, or prohibited (claims); newest evidence observed 2026-10-01, no evidence, and max_evidence_age_days unset (evidence); draft missing the sender identity (sender_identity), the postal address (postal_address), the opt-out line (opt_out), or the configured ad identification (ad_identification).
- [x] With approvals missing, the contact ineligible, evidence stale and the draft lacking every configured value, prepare-send prints the refused lines in the order approval, eligibility, evidence, sender_identity, postal_address, opt_out, ad_identification and the prepare_refused payload lists them in that order; with sending.sender_identity or sending.postal_address empty in config the detail says 'not configured'; with no ad_identification configured a draft without one passes that check.
- [x] 'cottonwood prepare-send 99 DRAFT' with no lead 99 exits 1 with a stderr line starting 'error: lead:' and appends no activity; a voided lead approval (a correction voiding it) counts as no approval.
- [x] uv run pytest, uv run ruff check ., uv run mypy . and uv run ruff format --check . all pass.

All criteria verified 2026-11-15.

## Depends on
CCGE-130
