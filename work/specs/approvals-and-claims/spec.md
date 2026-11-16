# Approvals And Claims — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
Phase 5 (gated outreach loop) needs founder approvals and a claims library before any draft can be prepared for sending, and an address must be suppressible without a lead. Today there is no `approve` command, no claims file and no `suppress` command: nothing records the founder's written approval of a lead, a draft, a claim, an audience or an offer (R-18); nothing lists the outreach claims with their status, evidence and verifier, or stops a claim from becoming `verified` without a founder claim approval (R-19); and an opt-out that arrives outside a lead cannot be recorded (R-24). The feature `send-gate` (`prepare-send`, `log-outreach`, `log-reply`) builds on all three (docs/cottonwood-growth-engine.md R-18, R-19, R-24; work/initiatives/cottonwood-growth-engine/architecture.md, gate.py and config/claims.yaml; roadmap phase 5).

## Goals / non-goals
- Goal: `cottonwood approve SCOPE ITEM` records a founder approval with approver, approval date, scope (`lead`, `draft`, `claim`, `audience` or `offer`), the item approved and a reference to the founder's written approval, as an append-only `approval` activity; it refuses without that reference (R-18).
- Goal: a draft approval names its lead and records the draft file's SHA-256, so `send-gate` can tell whether the approved draft is the one being sent.
- Goal: `config/claims.yaml` lists each outreach claim with id, text, status (`verified`, `unverified`, `prohibited`), evidence or source, `verified_by` and `verified_at`, and ships with the five R-19 claims marked `unverified` (R-19).
- Goal: a claim counts as `verified` only when the file marks it verified and a recorded claim approval matches it; `approve claim ID` records the approval and a `claim_verified` activity, and `cottonwood claims` shows each claim's effective status and names every mismatch between the file and the recorded approvals (R-19).
- Goal: `cottonwood suppress EMAIL --reason TEXT` adds a normalized address to suppression without a lead; an existing entry is left exactly as it is (R-24).
- Non-goal: `prepare-send`, `log-outreach`, `log-reply` and the gate checks that use approvals, claims and suppression (feature `send-gate`); the `prepare-outreach` skill and its claims list (feature `outreach-skill`).
- Non-goal: revoking an approval or un-verifying a claim with a command (a correction can void an activity; the founder edits the claims file), and changing contact eligibility when an address is suppressed (every send-path check reads suppression directly, R-24).
- Non-goal: deciding the claims' truth. The five shipped claims stay `unverified` until the founder answers the open questions (docs/cottonwood-growth-engine.md, open questions before first send).

## User stories
### US-1 — Record a founder approval with its written reference
As the developer, I want to record each founder approval with who approved what, when, and a reference to the founder's written approval, so that every gated step can point to a real sign-off.

Acceptance criteria:
- AC-1.1: With utc_now pinned to 2026-12-01T00:00:00Z and lead 1 stored, `cottonwood approve lead 1 --approver "Founder" --reference "email 2026-11-29 Re: first prospects"` exits 0, prints `approval 1 recorded: lead 1 by Founder`, and appends one `approval` activity with lead_id 1 whose payload has scope `lead`, item `1`, approver `Founder`, reference `email 2026-11-29 Re: first prospects` and approved_on `2026-11-30` (today in America/Denver); `--date 2026-11-29` records approved_on `2026-11-29`.
- AC-1.2: `cottonwood approve draft out/drafts/1-1.md --lead 1 --approver Founder --reference "email 2026-11-30 Re: draft 1"` for an existing draft file exits 0, prints `approval N recorded: draft out/drafts/1-1.md for lead 1 by Founder`, and stores scope `draft`, item `out/drafts/1-1.md`, lead_id 1 and the payload field `sha256` equal to the SHA-256 hex digest of the file's bytes.
- AC-1.3: `approve audience "Salt Lake County property managers" ...` and `approve offer "free walkthrough" ...` exit 0 and store scope `audience` / `offer` with that text as the item and no lead (lead_id NULL), unless `--lead N` is given.
- AC-1.4: Each of these exits 1, prints one stderr line starting `error: FIELD:` naming the field, and appends no activity: a missing or blank `--reference` (`error: reference:`); a blank `--approver` (`error: approver:`); `approve lead 99` with no lead 99 and `approve lead abc` (`error: lead:`); `approve draft` without `--lead` (`error: lead:`) or with a file that does not exist (`error: draft:`); a blank audience or offer item (`error: item:`); `--date 2026-12-01` (after today) or `--date 30/11/2026` (`error: date:`); a `--lead` that does not exist. A scope other than the five is refused by argparse with exit 2.

### US-2 — A claims library where only a founder approval verifies a claim
As the developer, I want the outreach claims in one reviewed file whose `verified` status is honored only when a founder claim approval backs it, so that a draft can never rely on a claim the founder did not verify.

Acceptance criteria:
- AC-2.1: `config/claims.yaml` exists and loads; it lists exactly five claims with ids `fashion-place-attribution`, `service-area`, `license-classification`, `insurance-bonding` and `prior-company-experience`, each with non-empty text, status `unverified`, a non-empty `evidence` naming the open question or source, and `verified_by` and `verified_at` null.
- AC-2.2: The loader refuses, exiting 1 with an `error:` line naming the file and the claim's index or id and the field, a claims file where: a claim id is missing, duplicated or not lower-kebab-case; text or evidence is blank; status is not one of the three; a `verified` claim lacks `verified_by` or a `YYYY-MM-DD` `verified_at`; or an `unverified` or `prohibited` claim has `verified_by` or `verified_at` set.
- AC-2.3: `cottonwood approve claim service-area --approver Founder --reference "email 2026-11-30 Re: claims"` exits 0, prints `approval N recorded: claim service-area by Founder; mark it verified in config/claims.yaml with verified_by: Founder and verified_at: 2026-11-30`, and appends in one transaction an `approval` activity (scope `claim`, item `service-area`) and a `claim_verified` activity whose payload has claim_id `service-area`, the approval's activity id, verified_by `Founder` and verified_at `2026-11-30`. `approve claim` exits 1 with `error: claim:` and appends nothing for an id not in the file, for a `prohibited` claim, and for a claim that already has a claim_verified activity no correction voids.
- AC-2.4: `cottonwood claims` prints one line per claim, `ID: STATUS` with the effective status, and exits 0 when the file and the recorded approvals agree. The effective status is `verified` only when the file says `verified` and an unvoided `claim_verified` activity for that id has the same verified_by and verified_at; `prohibited` when the file says so; otherwise `unverified`.
- AC-2.5: `cottonwood claims` exits 1 and names the claim on its line in each mismatch: the file marks a claim `verified` with no matching claim approval (`ID: unverified (marked verified but no matching claim approval)`), or a claim has a claim approval while the file still says `unverified` (`ID: unverified (approved on DATE by NAME; mark it verified in the claims file)`). `--claims PATH` reads another claims file; the default is `config/claims.yaml`.

### US-3 — Suppress an address without a lead
As the developer, I want to suppress an email address that is not attached to any lead, so that an opt-out received by phone or from another channel is honored everywhere suppression is checked.

Acceptance criteria:
- AC-3.1: With utc_now pinned to 2026-12-01T00:00:00Z, `cottonwood suppress " Alice@Example.COM " --reason "asked by phone"` exits 0, prints `suppressed alice@example.com`, and stores one suppression row with email_norm `alice@example.com`, reason `asked by phone`, source `suppress` and added_at `2026-12-01T00:00:00Z`; `--source "phone call"` stores that source instead.
- AC-3.2: Suppressing an address that is already suppressed exits 0, prints `alice@example.com already suppressed since 2026-11-30 (asked by phone)` (the added date in America/Denver and the stored reason) and leaves the stored row unchanged.
- AC-3.3: A blank `--reason` (`error: reason:`) or an address that is blank or does not have exactly one `@` with text on both sides (`error: email:`) exits 1 and stores nothing; after a successful `suppress`, `prospects-import` of a record with that contact email imports the contact as `ineligible`, and `set-eligibility` refuses `eligible` for it.

### US-4 — Checks
Acceptance criteria:
- AC-4.1: `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

## Constraints & assumptions
- Approvals and claim verifications are rows in the append-only `activities` table (architecture decision 9: types `approval`, `claim_verified`); no new table and no migration.
- The approval date is the day of the founder's written approval in America/Denver, not after today; it defaults to today (R-32).
- The claims file is YAML in `config/` (architecture decision 5) and is edited by hand; the CLI never rewrites it. A claim is verified only when the file and a recorded claim approval agree, so neither a hand edit alone nor an approval alone verifies it (R-19).
- `suppress` writes only the suppression table (which outlives contact deletion, R-35) and stores no email address in activities.
- Every command makes no network call and exits 0 done, 1 refused, 2 usage (architecture).

## Success metrics
- The phase-5 exit criteria for this feature hold: `approve` refuses without a written-approval reference; claims become `verified` only through a claim approval; `suppress` works without a lead (roadmap phase 5).
