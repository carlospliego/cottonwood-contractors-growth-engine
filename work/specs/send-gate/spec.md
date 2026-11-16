# Send Gate — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
Approvals, the claims library and suppression exist (feature `approvals-and-claims`), but nothing turns an approved draft into something the founder may send, and nothing records what was sent or what came back. Phase 5 needs the deterministic send gate: `prepare-send` is the only producer of a sendable draft and refuses, naming every failed check, unless the founder approved the lead and that exact draft, the contact is eligible and not suppressed, every claim used is verified, the evidence is fresh, and the draft carries the configured sender identity, postal address, opt-out line and ad identification (R-21). `log-outreach` records a send the founder performed and flags any send that bypassed the gate (R-22). `log-reply` records a reply and, in the same command, suppresses an opt-out and makes a bounced contact ineligible (R-23) (docs/cottonwood-growth-engine.md R-21–R-24; architecture decisions 4, 6, 9, 10; roadmap phase 5).

## Goals / non-goals
- Goal: a `sending:` section in `config/pilot.yaml` holds `sender_identity`, `postal_address`, `opt_out_line` and optional `ad_identification`; it ships unset, and `prepare-send` refuses while sender identity or postal address is empty (R-21).
- Goal: `cottonwood/schemas/draft-claims.schema.json` defines the claims list that accompanies a draft (`<draft stem>.claims.json`: a JSON array of `{claim_id, status}`), which `prepare-send` reads and the `outreach-skill` feature will write.
- Goal: `cottonwood prepare-send LEAD DRAFT` writes `out/send/<draft file name>` (a byte-for-byte copy of the draft) and records a `draft_prepared` activity only when every R-21 check passes; otherwise it writes nothing, records a `prepare_refused` activity naming the failed checks, prints one `refused: CHECK: detail` line per failed check and exits 1.
- Goal: `cottonwood log-outreach LEAD` records a `sent` activity for a send the founder performed (recipient match, public source URL, message digest, sender, send date, optional provider message ID, prepared-draft reference); a send with no matching prepared draft, a different message, a different recipient, or a recipient suppressed since preparation also records a `gate_violation` activity and exits 1 (R-22).
- Goal: `cottonwood log-reply LEAD TYPE` records a `reply` activity of type `interested`, `not_now`, `not_relevant`, `referral`, `opt_out`, `bounce` or `other`; `opt_out` adds the contact's address to suppression and `bounce` sets the contact `ineligible`, in the same transaction (R-23, R-24).
- Non-goal: sending email, any mail credential or provider call (R-27: the founder sends from their own client); the `prepare-outreach` skill and `review --lead --json` (feature `outreach-skill`).
- Non-goal: deciding the sender identity, postal address, opt-out wording, ad identification or maximum evidence age; these are founder questions, and the gate stays closed until they are configured.

## User stories
### US-1 — Configure what every sendable draft must carry
As the developer, I want the sender identity, postal address, opt-out line and ad identification in the pilot config, so that the gate checks every draft against the founder's approved wording and stays closed until it is set.

Acceptance criteria:
- AC-1.1: `config.load_config` reads an optional `sending:` mapping with `sender_identity`, `postal_address`, `opt_out_line` and `ad_identification` (strings); a missing section or key loads as empty, and a non-string value or a non-mapping section is refused with a `ConfigError` naming `sending.KEY`. The shipped `config/pilot.yaml` documents the section with every key commented out.
- AC-1.2: `cottonwood/schemas/draft-claims.schema.json` is a JSON Schema for an array of objects with required string `claim_id` (lower-kebab-case) and `status` (one of `verified`, `unverified`, `prohibited`) and no other properties; a loader validates a claims list against it and refuses a file that is missing, not JSON or not valid, naming the file.

### US-2 — Prepare a sendable draft only through the gate
As the developer, I want `prepare-send` to produce the only sendable copy of a draft and to refuse, naming every failed check, unless every R-21 condition holds, so that nothing unapproved, unverified, stale, suppressed or non-compliant can reach the founder's outbox.

Acceptance criteria:
- AC-2.1: With utc_now pinned to 2026-12-01T00:00:00Z, a config with all four sending values and `review.max_evidence_age_days: 30`, a direct_candidate lead 1 whose contact is `eligible` with an unsuppressed email, evidence observed 2026-11-20, an unvoided `approval` of scope `lead` for lead 1, an unvoided `approval` of scope `draft` for lead 1 whose sha256 matches DRAFT, DRAFT containing the sender identity, postal address, opt-out line and ad identification, and a claims list naming only claims whose effective status is `verified`: `cottonwood prepare-send 1 DRAFT --claims CLAIMS` exits 0, writes `out/send/NAME` (NAME the draft's file name, under `--out DIR`, default `out/send`) byte-identical to DRAFT, prints `sendable draft written: out/send/NAME (prepared N)`, and appends one `draft_prepared` activity (lead_id 1, contact_id the contact) whose payload has draft, sha256, sendable, claim_ids and the two approval activity ids.
- AC-2.2: Each of these, alone, makes `prepare-send` exit 1, write no file under the output directory, print a stderr line starting `refused: CHECK:` for that check, and append one `prepare_refused` activity whose payload lists the failed check names: no unvoided lead approval (`approval`); no unvoided draft approval for that lead, or one whose sha256 differs from the draft (`approval`); the contact not `eligible` or the lead without a contact email (`eligibility`); the contact's address suppressed (`suppression`); the claims list missing or invalid (`claims`); a claim not in the claims file, not effectively `verified`, or `prohibited` (`claims`); no evidence, newest evidence older than the maximum age, or no maximum age configured (`evidence`); the draft lacking the configured sender identity (`sender_identity`), postal address (`postal_address`), opt-out line (`opt_out`) or, when configured, ad identification (`ad_identification`).
- AC-2.3: When several checks fail, every failed check is printed and listed (one line per failure, in the order of AC-2.2); an empty `sending.sender_identity` or `sending.postal_address` in config fails `sender_identity` / `postal_address` with a detail saying it is not configured; a lead id with no lead exits 1 with `error: lead:` and records nothing.

### US-3 — Record what was sent and flag a bypass
As the developer, I want to log each send the founder performed and have the CLI flag any send that did not go through `prepare-send`, so that the report and the audit trail show gate violations.

Acceptance criteria:
- AC-3.1: After a successful `prepare-send` recorded as activity P, `cottonwood log-outreach 1 --prepared P --recipient CONTACT_EMAIL --source-url https://firm.example.com/team --message out/send/NAME --sender Founder --date 2026-11-30 --provider-message-id abc123` exits 0, prints `send recorded: lead 1 (activity N)`, and appends one `sent` activity (lead_id 1, contact_id the contact) whose payload has prepared P, source_url, the message's sha256, sender, sent_on `2026-11-30`, provider_message_id `abc123` and recipient_matches true; no email address is stored in the payload.
- AC-3.2: Each of these records the `sent` activity and also a `gate_violation` activity (payload: the sent activity id and the reasons), prints one `gate violation: REASON` stderr line per reason and exits 1: no `--prepared` (`no prepared draft`); `--prepared` naming an activity that is not a `draft_prepared` for this lead (`no prepared draft`); a message file whose sha256 differs from the prepared draft (`message differs from the prepared draft`); a recipient whose normalized address differs from the prepared contact's (`recipient differs from the prepared contact`); a recipient suppressed after the preparation (`recipient suppressed since preparation`).
- AC-3.3: A blank `--sender`, a `--source-url` that is not an http(s) URL, a missing message file, a `--date` after today or malformed, or no lead with that id exits 1 with `error: FIELD:` and records nothing.

### US-4 — Record replies, honoring opt-outs and bounces at once
As the developer, I want `log-reply` to record each reply and, for an opt-out or a bounce, update suppression or eligibility in the same command, so that no later send can reach someone who opted out or an address that bounced.

Acceptance criteria:
- AC-4.1: `cottonwood log-reply 1 interested --date 2026-11-30 --note "wants a call"` exits 0, prints `reply recorded: lead 1 interested (activity N)` and appends one `reply` activity with payload type, received_on and note; each of the seven types is accepted and any other type is refused by argparse with exit 2.
- AC-4.2: `log-reply 1 opt_out` adds the lead contact's normalized email to suppression (reason `opt-out reply to lead 1`, source `log-reply`), appends the `reply` and a `suppressed` activity (no email in its payload), and prints a second line `suppressed: contact C`; an already-suppressed address leaves its row unchanged; afterwards `prepare-send` for that lead fails `suppression`.
- AC-4.3: `log-reply 1 bounce` sets the lead's contact `ineligible` and appends the `reply` and an `eligibility_set` activity in the same transaction, printing `contact C: eligibility eligible -> ineligible`; `opt_out` or `bounce` on a lead with no contact email exits 1 with `error: contact:` and records nothing.

### US-5 — Checks
Acceptance criteria:
- AC-5.1: `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

## Constraints & assumptions
- Sends, refusals, violations and replies are rows in the append-only `activities` table (architecture decision 9: `draft_prepared`, `prepare_refused`, `sent`, `gate_violation`, `reply`, `suppressed`); no migration.
- No email address is written to `activities`; recipient checks compare normalized addresses and store only whether they matched (contact data stays in `contacts` and `suppression`, R-35).
- A draft approval covers a draft only when its stored sha256 equals the draft file's sha256 (feature `approvals-and-claims`); `prepare-send` copies the approved bytes unchanged, so `log-outreach` can compare the sent message's sha256 with it.
- A claim's effective status comes from `claims.effective_statuses` (the claims file and recorded claim approvals); the `status` a draft's claims list states is informational and never trusted.
- An unset maximum evidence age fails the `evidence` check: sending stays blocked until the founder decides it.
- The CLI never sends email and makes no network call (R-27).

## Success metrics
- The phase-5 exit criteria for this feature hold: `prepare-send` writes a sendable draft only when every R-21 check passes and names each failed check otherwise; `log-outreach` records a send and flags a bypass as a gate violation; `log-reply` opt-out suppresses and bounce makes ineligible in the same command (roadmap phase 5).
