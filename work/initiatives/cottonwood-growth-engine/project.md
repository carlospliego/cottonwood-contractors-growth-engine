# Cottonwood Growth Engine — project

Source: `docs/cottonwood-growth-engine.md` (approved spec, 35 requirements R-1…R-35). Background draft: `SPEC.md` v1.2.

## Why now
- Cottonwood is an early-stage Utah GC that wants $50,000+ commercial work, but it may be losing website and phone inquiries without knowing it, and it has no repeatable way to start credible commercial conversations.
- The founder has 5–10 sales hours a week, so research and drafting have to be done for them, with evidence attached, before any of their time is spent.
- The draft spec targets a functioning, measured acquisition loop within about 30 days. Each week without it is a week of inquiries that may go unlogged and prospects that go unresearched.

## Outcomes (measurable)
Each outcome maps to the spec's success conditions. Software outcomes are pass/fail. The market outcome is measured, not promised.

1. **Inbound captured:** a labeled test form inquiry and a labeled test phone inquiry each appear as a lead in the `review` output sent to the founder (R-1, R-3, R-13).
2. **Evidence-backed prospects:** a hand-reviewed set of direct and relationship prospects exists. Every one has evidence within the configured maximum age, and none is marked `fabricated` (R-5–R-11). No minimum count is required.
3. **Gated outreach loop:** at least one founder-approved email has gone through `approve` → `prepare-send` → founder send → `log-outreach` → reply or no-reply logged → handoff brief, with zero gate violations (R-18–R-24). If the open founder facts block sending, this outcome is instead "the report states the blocking question" (spec, Decisions: Blocked sending).
4. **Honest reporting:** the 30-day report covers every R-28 metric and the KPI, with zeros printed. Observed outcomes are kept apart from estimates (R-28, R-29).
5. **Within budget:** recurring cost stays ≤ $500/month (from `log-cost` and recorded model cost). The tool needs no more than 10–20 developer hours and 5–10 founder sales hours a week to run.
6. **Market signal (measured, not an acceptance gate):** the month-one KPI, (qualified direct conversations + partner conversations) ÷ founder hours, is reported. Zero is a valid result.

## Scope (in / out)
**In:** the 35 spec requirements. That covers inbound logging, prospect import with validation and dedupe, hand review, review queues, the event/stage log, founder approval and claims, `prepare-send` with every pre-send check, outreach, reply and suppression logging, the two Claude skills (research, outreach drafting with founder brief), run recording, the Markdown report, backup, and the runbook (inbound checklist, restore, deletion requests).

**Out:** the spec's Non-goals list applies in full. In particular: any scheduled or automated step, Formspark import/API/webhooks, programmatic sending, SMS/calls/DMs, run blocking or a kill switch, CSV output, a restore command, live website changes beyond founder-approved corrections, platforms or multi-tenancy, dashboards, scraping, and estimating or contracting.

## Stakeholders & decision owners
| Decision | Owner |
|---|---|
| Business facts, claims, audiences, offers, each draft, walkthrough capacity, cost-cap amounts, maximum evidence age, Gate 1 threshold | Founder (in writing, recorded with `approve` where the spec requires it) |
| Architecture, tooling, schema, CLI behavior within the spec | Developer |
| GA4/Formspark fact-finding | Developer with the founder |
| Changing the spec or the roadmap | Founder and developer together |

## Constraints
- Recurring cost ≤ $500/month, including model calls and outreach tools.
- Developer 10–20 h/week and founder 5–10 sales h/week.
- CAN-SPAM for commercial email. Opt-outs are honored as soon as they're logged, the same day they arrive.
- Never invent prospects, needs, budgets, contacts or credentials.
- The tool runs on the developer's macOS machine with FileVault on, using SQLite, a current Python 3 and no server.
- No email-sending credentials anywhere in the tool's environment.
- The 11 open questions in the spec are founder-owned. The ones marked "before first send" gate outcome 3, but not the build.
