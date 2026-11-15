# Inbound Logging — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
Cottonwood's website form (Formspark) and phone are its only inbound channels, and today an inquiry lives only in the founder's inbox or call log. The developer, who operates the tool, needs to log each inquiry the same working day it is relayed (docs/cottonwood-growth-engine.md:19), without inventing fields, without double-logging the same person twice in a day, and with test submissions kept apart from real counts. Solved when the labeled test form inquiry and test phone inquiry appear labeled in the `review` file sent to the founder and drop out of every count (verification.md outcome 1), and the runbook carries the inbound checklist and relay procedure (R-4).

## Goals / non-goals
- Goal: `cottonwood log-inbound` records form and phone inquiries with only the supplied fields (R-1).
- Goal: a same-day duplicate (normalized email or E.164 phone, America/Denver date) warns and needs explicit confirmation (R-2).
- Goal: test inquiries are labeled, shown labeled in `review` and excluded from counts (R-3); `review` can write to a file (R-31).
- Goal: `docs/runbook.md` gains the inbound verification checklist and the relay procedure (R-4).
- Non-goal: the direct-candidate and relationship-prospect queues in `review` (R-13 checklist and ordering) — phase 4, prospect-review.
- Non-goal: `report` and its counts (phase 3); this feature supplies the non-test filter it will reuse.
- Non-goal: pulling submissions from Formspark automatically, events such as acknowledgement or calls (`log-event`, phase 3).

## User stories
### US-1 — Log an inbound inquiry
As the developer, I want to record a relayed form or phone inquiry with only what the inquirer told us, so that the lead history is accurate and nothing is guessed.

Acceptance criteria:
- AC-1.1: After `cottonwood migrate`, the database is at the newest version and `leads` has a nullable `project_scope` column.
- AC-1.2: `cottonwood log-inbound --channel form --received "2026-11-16 09:30" --segment commercial --name "Pat Lee" --email Pat@Example.com` exits 0 and creates one `leads` row with type `inbound_inquiry`, stage `candidate`, channel `form`, segment `commercial`, `received_at` `2026-11-16T16:30:00Z`, is_test 0, and NULL `project_scope`, `value_amount`, `value_basis` and `property_location`; its contact has name `Pat Lee`, email `Pat@Example.com`, email_norm `pat@example.com` and NULL phone_e164.
- AC-1.3: With `--phone "(801) 555-0134" --scope "lobby refresh" --budget 25000 --location "Murray, UT" --company "Acme Holdings"`, the lead stores project_scope `lobby refresh`, value_amount `25000`, value_basis `buyer-stated`, property_location `Murray, UT` and an organization_id whose organization name is `Acme Holdings`; the contact stores phone_e164 `+18015550134`. A second inquiry with `--company "ACME holdings"` reuses that organization.
- AC-1.4: Each logged inquiry appends exactly one `inquiry_logged` activity for the lead whose payload contains channel, segment and is_test and contains none of the name, email, phone, scope or budget values.
- AC-1.5: `--received` also accepts a UTC timestamp ending in Z (`2026-11-16T16:30:00Z` stores the same value); a missing `--received`, `--channel` or `--segment`, or a channel or segment outside the allowed values, exits non-zero and writes no row.
- AC-1.6: An invalid email, an invalid phone, a non-decimal or negative budget, an unparseable `--received`, or no name, email or phone at all exits 1 with a message naming the field, and writes no lead, contact, organization or activity row.
- AC-1.7: `--test` stores is_test 1 and the success message includes `TEST`.

### US-2 — Catch same-day duplicates
As the developer, I want a warning when an inquiry matches one already logged that day, so that one person's form submission and follow-up call don't become two leads by accident.

Acceptance criteria:
- AC-2.1: When an existing `inbound_inquiry` lead's contact has the same email_norm or phone_e164 and its received_at falls on the same America/Denver date, `log-inbound` prints a warning naming each matching lead id, and without confirmation exits 1 and writes nothing (non-interactive stdin).
- AC-2.2: With `--confirm-duplicate`, the same inquiry is saved (exit 0) and its `inquiry_logged` payload lists the matching lead ids.
- AC-2.3: On an interactive terminal, answering `y` or `yes` to the prompt saves the inquiry; any other answer exits 1 and writes nothing.
- AC-2.4: A match on a different America/Denver date — including 2026-11-16 23:30 local versus 2026-11-17 00:30 local, which share a UTC date — produces no warning and saves normally; matching compares normalized values (`PAT@example.com ` matches `pat@example.com`; `801.555.0134` matches `(801) 555-0134`).

### US-3 — Review inquiries with tests labeled and excluded
As the developer, I want a review of inbound inquiries I can send to the founder, so that the founder sees every inquiry while test submissions never inflate the numbers.

Acceptance criteria:
- AC-3.1: `cottonwood review` prints Markdown with an `## Inbound inquiries` section listing one row per inquiry, newest received first, with lead id, received time in America/Denver (`YYYY-MM-DD HH:MM -07:00`), channel, segment, stage and the supplied contact fields; empty fields print as `—`.
- AC-3.2: Each test inquiry's row carries the label `TEST`; non-test rows do not.
- AC-3.3: The section's count line counts only non-test inquiries, by channel and by segment, and states how many test inquiries were excluded; with one test form and one test phone inquiry and one real form inquiry it reports 1 inquiry (form 1, phone 0) and 2 tests excluded. Zero counts print as 0.
- AC-3.4: `cottonwood review --out out/review.md` writes the same Markdown to that path (creating missing parent folders), prints the path, and exits 0; with no database file it exits 1 with a message.
- AC-3.5: A contact cleared by a deletion request (deleted_at set, fields NULL) still lists its lead with `—` for the cleared fields and no error.

### US-4 — Runbook for the inbound channel
As the developer and founder, we want the inbound checks and the relay procedure written down, so that Gate 0 can be signed off item by item.

Acceptance criteria:
- AC-4.1: `docs/runbook.md` has an `## Inbound verification checklist` section listing each R-4 item: a labeled commercial test submission, a labeled residential test submission, the spam/blocked-submission path, the notification spam-folder check, Formspark account owner, plan, limits and submission retention, the auto-forward to the developer, the mobile form and phone-link check, missed-call handling and owner, same-working-day response capacity, and GA4 vs privacy-page reconciliation — each with `checked_at`, `result` and `owner` fields.
- AC-4.2: `docs/runbook.md` has an `## Relay` section stating that Formspark notifications and outreach-mailbox replies are auto-forwarded (or CC'd) to the developer, the founder sends a daily note covering calls and in-person events, everything is logged the same working day and opt-outs the same day, and giving `cottonwood log-inbound` example commands for a form and a phone inquiry (including `--test` for checklist submissions).
- AC-4.3: The runbook no longer says later features add the inbound checklist and relay sections, and its existing restore, re-apply and deletion-request sections are unchanged (their tests still pass).

## Constraints & assumptions
- Timestamps stored in UTC, displayed in America/Denver (R-32); helpers in `cottonwood/timeutil.py`.
- Assumptions 1–7 in `assumptions.md` (build answered with its recommendations): project_scope column via migration 003 and buyer-stated budget; required `--received`; duplicate confirmation by prompt or `--confirm-duplicate`; duplicate keys and tests included; a contact per inquiry, organization reused by name_norm; `review` inbound section only; required fields and personal-data-free payloads.
- Generated review files contain contact data; `out/` is git-ignored (.gitignore line 20).

## Success metrics
- The phase 2 exit check: a labeled test form inquiry and a labeled test phone inquiry logged with `log-inbound` show as `TEST` in `review` output and are excluded from its counts; a same-day duplicate is refused without confirmation.

## Open questions
- None for the software; the checklist items' answers (Formspark owner, GA4, missed-call owner) are the founder's and are filled in the runbook.
