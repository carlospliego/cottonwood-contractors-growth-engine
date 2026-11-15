# Cottonwood Growth Engine — spec

Source draft: `SPEC.md` v1.2 (reviewed 2026-11-14). Facts it records "as checked November 14, 2026" are point-in-time and must be rechecked before they are relied on.

## Goal
Cottonwood Contractors is an early-stage Utah general contractor that wants commercial work, preferably $50,000+ projects, with smaller $10,000–$50,000 commercial work where viable and residential inbound continuing. It may be losing website and phone inquiries without knowing it, and it has no repeatable way to start credible commercial conversations; the founder owns sales and estimates with only 5–10 hours a week for sales. This pilot is a small Cottonwood-only tool that makes sure every inquiry lands in a lead record, lets Claude research evidence-backed direct-project and referral prospects and draft outreach that passes recorded founder approval and deterministic checks before the founder sends it by hand, logs replies, opt-outs, founder time and costs, and produces a report of what actually happened, zeros included.

It worked when, within about 30 days:
- a labeled test inquiry from the live website form and a labeled test phone inquiry each appear as a lead in the `review` output sent to the founder;
- a reviewed set of real direct and relationship prospects exists, every one with evidence no older than the configured maximum age and none marked fabricated in hand review (no minimum count is required);
- at least one founder-approved B2B email has been prepared with `prepare-send`, sent, logged, and its reply (or absence of one) and any opt-out recorded, with each reply handed off to the founder as a brief — or, if sending stays blocked, the report states which open question blocks it while research and founder introductions continue;
- the 30-day report shows attempts, replies by type, qualified conversations, the month-one KPI, founder hours and cash/model cost, including zeros.

The month-one KPI is (qualified direct conversations + partner conversations) ÷ founder hours, as defined in R-28. It is measured, not promised: zero is a valid, reported result.

## Users and main flows
- **Developer** (10–20 h/week): builds the tool in this repo with Claude Code and operates it on their own machine — logs inquiries, calls and replies, runs the Claude skills, imports prospects, records founder approvals, prepares sendable drafts, takes backups, and sends the founder the review, briefs and reports.
- **Founder** (5–10 sales h/week): receives Formspark notifications and calls directly and acknowledges inquiries, gives written approval of audiences, offers, claims and drafts, sends prepared drafts from Cottonwood's monitored mailbox, runs remote screens and walkthroughs, and sends the developer a short daily note of calls, missed calls and outcomes.
- **Relay:** Formspark notifications and replies to the outreach mailbox are auto-forwarded (or CC'd) to the developer; the founder's daily note covers calls and in-person events. The developer logs everything the same working day it arrives, and opt-outs the same day.
- **Inbound flow:** website form or phone inquiry → founder notified and acknowledges (target: same working day, as the site promises) → developer logs the inquiry and the acknowledgement → remote qualification → founder decides on a walkthrough or estimate.
- **Direct-candidate flow (Motion A):** founder-approved source → Claude research skill gathers evidence and separates facts from hypotheses → validated import → hand review → review queue → founder approves the draft in writing → `prepare-send` → founder sends → reply logged and brief handed to founder → 10–15 minute remote screen → qualified only on prospect-confirmed need or a documented accessible procurement → optional 30–60 minute walkthrough → proposal only with founder approval.
- **Relationship flow (Motion B):** property manager, landlord, broker, tenant rep or designer identified with a verified professional contact → founder-approved introduction via `prepare-send` → response → vendor-process conversation → periodic approved follow-up → any referred job recorded as a new direct or inbound lead linked to the referring partner.
- **Weekly flow:** the developer runs the report and sends it to the founder, who reviews it together with the queue.

## Requirements
### Inbound
- R-1: `cottonwood log-inbound` records a website-form or phone inquiry as an `inbound_inquiry` lead with channel (`form` or `phone`), received time, segment (`commercial`, `residential` or `unknown`, as the inquirer stated), and only the fields the inquirer supplied; project scope and budget stay empty unless the inquirer stated them.
- R-2: An inquiry whose normalized email or E.164 phone matches an existing inquiry received on the same local (America/Denver) date prints a duplicate warning and requires explicit confirmation before saving.
- R-3: Inquiries marked as tests carry a test label, are listed in `review` with that label, and are excluded from every count in `report`.
- R-4: `docs/runbook.md` contains the inbound verification checklist — two labeled test submissions (one commercial, one residential), the spam/blocked-submission path, the notification spam-folder check, Formspark account owner, plan, limits and submission retention, the auto-forward to the developer, mobile form and phone-link check, missed-call handling and owner, same-working-day response capacity, and GA4 vs privacy-page reconciliation — each item with `checked_at`, result and owner fields.

### Prospects and evidence
- R-5: `cottonwood prospects-import <file>` accepts CSV or JSON records of type `direct_candidate` or `relationship_prospect`; each record must carry at least one evidence item with exact URL, observed date and excerpt or observation, and separate verified-fact and hypothesis fields.
- R-6: A record that fails validation is rejected with a message naming the record, the field and the rule that failed, and nothing from it is written; valid records in the same file are still imported; each rejection is counted as a data-quality failure.
- R-7: Re-importing the same file creates no duplicates. Organizations match on normalized domain (else normalized name), contacts on normalized email (else name plus organization), and leads on organization plus type plus property location. A matched record keeps its stored values, gains any new evidence, and the import prints each field whose incoming value differs.
- R-8: Contact eligibility is `eligible`, `ineligible` or `unknown`, stored as `unknown` unless set. `cottonwood set-eligibility <contact> eligible` requires a public professional source URL for the address and an unambiguous identity, refuses a suppressed address, and writes an activity recording the basis.
- R-9: Money values are stored as exact decimals with a basis of `buyer-stated`, `founder-estimated` or `unverified`; a money value without a basis is rejected.
- R-10: The maximum evidence age is a config value; `review` shows each lead's newest-evidence age, and `prepare-send` refuses a lead whose newest evidence is older than the maximum.
- R-11: `cottonwood mark-reviewed <lead-id>` records the hand-review result for a researched record as `relevant`, `irrelevant` or `fabricated` (unsupported by its evidence), with reviewer and date; `fabricated` results count as data-quality failures and the report shows hand-review counts per motion.
- R-12: A lead may carry an optional `referred_by` link to a relationship-prospect lead, and the report counts referred leads per referring partner.

### Review, stages and events
- R-13: `cottonwood review` prints separate sections for inbound inquiries, direct candidates and relationship prospects; each candidate row shows yes/no/unknown answers to the queue's checklist items in `config/pilot.yaml`, the evidence URL and age, the next action and estimated founder time in hours; candidates are ordered by count of `yes` answers, ties broken by lower founder time, and the output states this rule.
- R-14: Lead stages are limited to: direct/inbound `candidate`, `researched`, `contacted_or_replied`, `buyer_need_confirmed`, `walkthrough`, `proposal`, `won`, `lost`, `closed_no_fit`; relationship `identified`, `researched`, `introduced`, `responded`, `active_relationship`, `closed_no_fit`; any other value is rejected.
- R-15: `cottonwood log-event <lead-id> <type>` records an event of type `acknowledgement`, `call`, `missed_call`, `call_returned`, `remote_screen`, `walkthrough`, `proposal`, `won`, `lost`, `partner_conversation`, `handoff` or `note`, with its time, and optionally moves the lead to a new stage; every stage change is recorded as an activity naming the event that caused it.
- R-16: A lead enters `buyer_need_confirmed` only through a logged event stating either the prospect's confirmed need or the URL of an accessible active procurement.
- R-17: Activities cannot be edited or deleted; `cottonwood log-event <lead-id> correction --voids <activity-id>` marks an earlier activity void, and void activities are excluded from all counts.

### Approval, claims and sending
- R-18: `cottonwood approve` records a founder approval with approver, time, scope (`lead`, `draft`, `claim`, `audience` or `offer`), the item approved, and a reference to the founder's written approval (for example the email's date and subject); approvals cannot be recorded without that reference.
- R-19: A claims file in `config/` lists each outreach claim with status `verified`, `unverified` or `prohibited`, its evidence or source, `verified_by` and `verified_at`; a claim becomes `verified` only through a recorded founder approval of scope `claim`. It ships with the Fashion Place attribution, the four-county service area, license classification, insurance/bonding and prior-company project experience marked `unverified`.
- R-20: The outreach-drafting skill outputs a draft email, a JSON list of the claim IDs it uses with their status, and a short founder brief; any claim not present in the claims file with status `verified` is flagged, and the skill produces no draft for a suppressed contact.
- R-21: `cottonwood prepare-send <lead-id> <draft>` writes a sendable draft file only when: a founder approval covers the lead and that draft; the contact is `eligible` and not suppressed; every claim used is `verified` and none is `prohibited`; evidence is within the maximum age; and the draft contains the configured sender identity, valid business postal address, a working opt-out line and ad identification where configured. It refuses otherwise with a message naming each failed check, and refuses when the postal address or sender identity in config is empty.
- R-22: `cottonwood log-outreach <lead-id>` records a send the founder performed (recipient, public professional source, message, sender, send date, optional provider message ID, and the prepared-draft reference); a send with no matching prepared draft, or to an address suppressed since preparation, is recorded and reported as a gate violation.
- R-23: `cottonwood log-reply <lead-id> <type>` records a reply of type `interested`, `not_now`, `not_relevant`, `referral`, `opt_out`, `bounce` or `other`; `opt_out` adds the recipient to suppression and `bounce` sets the contact `ineligible`, each in the same command.
- R-24: Suppression is keyed on the normalized (trimmed, lower-cased) email address; `cottonwood suppress <email> --reason <text>` adds an address without a lead; suppression is checked by `prospects-import` (matching contacts are imported as `ineligible`), `set-eligibility`, the drafting skill and `prepare-send`, and entries are never deleted.

### Claude runs
- R-25: Research-skill output is validated by Python against a schema before import; invalid output is rejected under R-6, never repaired by guessing.
- R-26: Every Claude skill run is recorded with skill version, model, start and end time, input and output references, validation result, and token count and cost taken from a named source (Claude Code's `/cost` output or the billing console), marked `estimated` when not exact.
- R-27: No email-sending credentials exist in the repository, `.env` or tool config, and the research skill is given only web-research and file tools; text taken from web pages or pasted content is stored only as evidence data.

### Reports
- R-28: `cottonwood report --period 7d|30d` (or `--from`/`--to` dates, inclusive, America/Denver) writes a Markdown file with, for the period: inbound inquiries by channel and segment; acknowledgements within and outside the same-working-day target; missed and returned calls; researched direct candidates and partner firms and their hand-review counts; approvals; prepared drafts; sends; gate violations; replies by type; qualified direct conversations (leads entering `buyer_need_confirmed`); partner conversations (`partner_conversation` events); remote screens; walkthroughs; proposals; won projects; referred leads; founder hours; model cost against the configured monthly cap; other costs; opt-outs; data-quality failures; and the KPI (qualified direct conversations + partner conversations) ÷ founder hours, shown as `n/a` when hours are 0. Zero counts print as 0.
- R-29: The report shows observed outcomes separately from founder-estimated values and never counts a permit, vacancy, listing or email open as a qualified lead.
- R-30: `cottonwood log-time` and `cottonwood log-cost` record founder hours and spend with date and category, and the report totals them.
- R-31: `review` and `report` can write their output to a file for sending to the founder.

### Data
- R-32: All timestamps are stored in UTC and displayed in America/Denver time.
- R-33: `cottonwood backup` writes a consistent copy of the SQLite database to a configured local backup folder under a timestamped name, and fails with a clear message if the folder does not exist; `docs/runbook.md` documents the restore steps, including copying the current database aside first and checking the backup opens and contains the suppression table.
- R-34: The database file and backups are git-ignored, and secrets are read only from `.env`, with `.env.example` committed.
- R-35: `docs/runbook.md` documents the deletion-request procedure: remove the person's contact fields and notes, and keep their suppression entry.

## Decisions already made
- **Cottonwood only.** One application for this one business; no generic, multi-tenant or configurable-industry design. Cottonwood values live in `config/pilot.yaml`.
- **Approach:** one local Python CLI plus two interactive Claude Code skills (prospect research; outreach drafting with founder brief), over building automated collectors or a hosted service first. Reason: the founder's time and the $500/month cap favor a manual, evidence-first loop before anything is automated.
- **Storage:** a single SQLite file on the developer's machine, replacing the draft's PostgreSQL + Docker Compose. Reason: one operator, small volume; no server to run, and a backup is a file copy.
- **Operator:** the developer runs the CLI on their macOS machine (FileVault on) with a current Python 3; the founder receives files and does not run the CLI.
- **Relay:** auto-forwarding of Formspark notifications and outreach-mailbox replies to the developer, plus a daily founder note for calls; same-working-day logging. Reason: the developer operates the tool but the founder owns the inbox and phone.
- **Send gate:** founder approval is given in writing and recorded with `approve`; `prepare-send` runs every check before the email exists in sendable form; `log-outreach` flags sends that bypassed it. Reason: suppression and approval must be checked before sending, not after.
- **Cost caps are record-only:** per-run cost and month-to-date spend versus the cap are recorded and reported; nothing blocks a run. The developer stops running skills when spend nears the cap. There is no config kill switch.
- **Backups:** local copies only, to a configured folder on the same machine; Formspark remains the provider-side record of web inquiries. Accepted risk: losing the machine loses lead history not held in Formspark; Formspark retention is checked in the runbook (R-4).
- **Inbound ingestion:** manual logging from the forwarded Formspark notification or the call note, replacing export imports, the `inbound_submissions` table, the Formspark API and webhooks. The existing form and email notifications stay as they are.
- **Retention:** no automatic deletion during the pilot; the end-of-pilot review sets a retention period. Suppression entries are kept permanently.
- **Tables:** about seven — organizations, contacts, leads, evidence, activities (append-only, including approvals, events and corrections), agent_runs, suppression. No `send_outbox` until programmatic sending exists.
- **Outbound in V1:** Claude drafts; the founder reviews, approves in writing and sends B2B email from Cottonwood's monitored mailbox, plus founder-directed relationship contact. Founder approval is required before any outreach, pricing, commitment, proposal, commercial claim or permission change.
- **Opt-outs** take effect as soon as they are logged, the same day they arrive, although federal law generally allows up to 10 business days.
- **Offers:** direct candidates get a short remote fit call, then a complimentary 30–60 minute walkthrough only after remote qualification; partners get an introduction and a question about how they choose vendors. The default is at most 1–2 new walkthroughs a week; the founder can raise it.
- **Scoring:** transparent yes/no/unknown checklists in separate queues for direct and relationship prospects (items from SPEC.md §9, kept in `config/pilot.yaml`); no probability score or ML.
- **Sourcing:** manual, Claude-assisted research of public professional sources — brokerage listings, firm sites, business openings and relocations, local announcements. Permits are optional verification only; the Utah County ArcGIS permit service returned 404 on 2026-11-14 and is not a dependency.
- **First sample:** about 10 direct candidates and 10 partner prospects if genuine ones exist, with at least 5 from each motion hand-reviewed (R-11) before sending; there is no quota.
- **Gate 1 (evidence):** before the first send, the hand-review results of the first sample must meet the founder's false-positive threshold with zero `fabricated` results.
- **Blocked sending:** if outreach cannot be approved, research and founder introductions continue, sends stay blocked, and the report states the blocking open question.
- **Interface:** CLI plus Markdown files; no web UI, so there are no design files.
- **Languages:** Python for the tool; TypeScript only if the website itself changes.

## Non-goals
- Any scheduled, automated or unattended step during the pilot, including the draft's week-4 "automate one proven step"; that is reconsidered after the pilot.
- Importing Formspark exports, polling the Formspark API, or receiving webhooks.
- Automated or programmatic email sending, `send_outbox`, retry or reconciliation machinery, cold SMS, AI calling, social DMs, and auto-texting form submitters.
- Blocking or capping Claude runs automatically, or a kill-switch mechanism.
- CSV report output and a dedicated restore command.
- Changes to the live website during the pilot, except founder-approved corrections of inaccurate claims (such as the privacy statement or service area).
- Multi-tenant or generic platform features, billing, user accounts, a plugin system, or a workflow engine.
- More than the two Claude skills, agent-to-agent orchestration, or self-modifying prompts.
- Queues, event buses, microservices, vector databases, or data warehouses.
- Scraping permit portals, scraping behind logins, bypassing anti-bot controls, or buying commercial datasets or enrichment.
- A dashboard or CRM, a call-tracking subscription, multi-touch attribution, an SEO content factory, or paid ads.
- Auto-quoting, estimating, guarantees, contracting, or code/legal determinations.
- Adding website tracking or analytics before the GA4 vs privacy-page question is resolved, and ever sending names, contact details or project text to GA4.
- Describing Cottonwood as an established commercial GC, or presenting prior-employer projects as Cottonwood-completed work.

## Constraints
- Recurring operating cost at most $500/month, including model calls and outreach tools.
- Developer time is 10–20 h/week and founder sales time 5–10 h/week; the tool must not need more to operate.
- Commercial email must meet CAN-SPAM: accurate headers and subject, ad identification where appropriate, a valid business postal address, a working opt-out, and prompt suppression. Other state and channel rules are reviewed before live sending.
- Never invent prospects, projects, buyer need, budgets, contact details or business credentials; unknown is a valid value.
- Store only business-relevant contact data; keep secrets out of prompts, logs and git. Files sent to the founder contain business contact data only and go through Cottonwood's existing business email.
- Web pages and pasted text are untrusted input, never instructions to run commands, disclose secrets or send messages.
- If `claude -p` is used later, verify authentication, billing, allowed tools, timeouts, error handling and skill loading first; `--bare` changes skill discovery.
- New frameworks, services or vendors are added only when they meet an immediate pilot requirement.

## Open questions
Owner in brackets; "before first send" means it must be answered before the first real outreach email.
- [Founder, before first send] Cottonwood's legal entity, Utah contractor license classification, insurance and bonding, and permitted project types.
- [Founder, before first send] Whether Cottonwood was in fact the GC on the Fashion Place entrance concourse, and whether its images may be reused.
- [Founder, before first send] Service-area claim: the site advertises Salt Lake County, while prospecting targets Salt Lake, Utah, Davis and Weber counties.
- [Founder, before first send] Verified project references and photo rights, including which work was done at previous companies.
- [Founder, before first send] Sender identity, valid business postal address, and the monitored inbox for replies and bounces.
- [Developer with founder, week 1] Whether GA4 is deployed, which property and domain the reported traffic growth comes from, and whether the privacy page ("no analytics, cookies or tracking") is accurate.
- [Developer with founder, week 1] The Formspark account owner, plan, submission limits, retention, and spam/blocked-submission handling.
- [Founder, week 1] Whether the founder can meet the site's same-working-day response promise, and who returns missed calls and when.
- [Founder, before first walkthrough] Realistic weekly walkthrough capacity beyond the 1–2 default.
- [Founder, before first skill run] The per-run and monthly model-cost cap amounts.
- [Founder, before first send] The maximum evidence age and the Gate 1 false-positive threshold.
