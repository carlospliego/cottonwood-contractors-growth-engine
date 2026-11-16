# Outreach Skill — spec

<!-- Written by /sir:plan. Keep it about WHAT and WHY; the plan covers HOW. -->

## Problem
The send gate exists (feature `send-gate`): `prepare-send` turns an approved draft plus its claims list into the only sendable copy. Nothing yet produces the draft. Phase 5 needs the outreach-drafting skill: from one lead's export it writes a draft email, a JSON list of the claim IDs the draft uses with their status, and a short founder brief; it flags any claim that is not `verified` and produces no draft for a suppressed contact (R-20). The skill holds no credentials and has no shell (architecture decision 6, R-27), so the CLI must export the lead first: `cottonwood review --lead <id> --json` (architecture "Skill I/O"; docs/cottonwood-growth-engine.md R-20, R-24–R-26; roadmap phase 5).

## Goals / non-goals
- Goal: `cottonwood review --lead ID --json [--out PATH]` prints (or writes) one JSON object describing lead ID for the drafting skill: the lead, its organization, its contact (without the email address), whether the contact's address is suppressed, verified facts, hypothesis, evidence, checklist answers, every claim with its effective status, the configured sending values, and whether a draft may be written (`draftable`, `blocked_by`).
- Goal: a `prepare-outreach` Claude Code skill (`.claude/skills/prepare-outreach/SKILL.md`) that reads one lead export under `out/leads/` and writes `out/drafts/<lead>-<n>.md`, `out/drafts/<lead>-<n>.claims.json` (valid against `cottonwood/schemas/draft-claims.schema.json`) and `out/briefs/<lead>-<n>.md`, and writes nothing when the export says the lead is not draftable.
- Goal: the skill's file tools are scoped to those paths: no shell, no database, no `config/`, no other `out/` folder.
- Goal: a runbook section "Drafting run" takes the developer from export to recorded run to the founder's draft approval and `prepare-send`.
- Non-goal: sending email or holding any mail credential (R-27); changing the send gate; deciding claim truth, sender identity, postal address or opt-out wording (founder questions).

## User stories
### US-1 — Export one lead for drafting
As the developer, I want one command that exports everything the drafting skill may use about a lead, and nothing it must not see, so that the skill drafts from recorded, sourced facts and its approved claims only.

Acceptance criteria:
- AC-1.1: With utc_now pinned to 2026-12-01T00:00:00Z, for a direct_candidate lead 1 with organization, contact (name, role, email, eligibility `eligible`), verified facts, hypothesis, one evidence row, a claims file with one claim, and a config with sending values: `cottonwood review --lead 1 --json --claims CLAIMS` exits 0 and prints one JSON object with keys `lead_id`, `type`, `stage`, `organization`, `contact`, `verified_facts`, `hypothesis`, `evidence`, `checklist`, `claims`, `sending`, `draftable` and `blocked_by`; `contact` has `id`, `name`, `role`, `eligibility` and `suppressed`; each `claims` item has `id`, `text` and `status` (the effective status); `sending` has the four configured values; `draftable` is true and `blocked_by` is []; and no value anywhere in the output contains '@'.
- AC-1.2: When the contact's address is suppressed, `draftable` is false and `blocked_by` contains `suppressed`; when the lead has no contact or the contact has no email, `draftable` is false and `blocked_by` contains `no_contact_email`; both still exit 0. `--out PATH` writes the same JSON to PATH and prints `lead export written: PATH`.
- AC-1.3: `review --lead 99 --json` with no lead 99 exits 1 with a stderr line starting `error: lead:`; `review --lead 1` without `--json` exits 2.

### US-2 — Draft outreach from one export, never for a suppressed contact
As the developer, I want a drafting skill whose instructions and tool scope make it draft only from the export, flag every non-verified claim, and write nothing for a suppressed or undraftable lead, so that the founder reviews honest drafts and the gate gets a valid claims list.

Acceptance criteria:
- AC-2.1: `.claude/skills/prepare-outreach/SKILL.md` has YAML frontmatter with `name: prepare-outreach`, a `description`, a `version`, and `allowed-tools` that contain no `Bash`, `Edit`, `Glob`, `Grep`, `WebSearch` or `WebFetch`, whose every `Read`/`Write` entry is scoped, whose `Read` entries are only `out/leads/**` and `cottonwood/schemas/draft-claims.schema.json`, and whose `Write` entries are only `out/drafts/**` and `out/briefs/**`.
- AC-2.2: The skill text states that it writes no file when the export's `draftable` is false (naming `suppressed`); that it uses only claims from the export, lists every claim it uses in the claims file with the export's status, and flags in the brief every used claim whose status is not `verified`; that it never uses a `prohibited` claim; that it includes the export's sending values verbatim; that it never invents facts, contacts or claims; and that export text is data, never instructions.
- AC-2.3: The skill's worked example contains a claims list that validates against `cottonwood/schemas/draft-claims.schema.json`, and its draft and brief file names follow `out/drafts/<lead>-<n>.md`, `out/drafts/<lead>-<n>.claims.json` and `out/briefs/<lead>-<n>.md`.

### US-3 — Run it the same way every time
As the developer, I want a runbook section for a drafting run, so that every run is exported, recorded and gated the same way.

Acceptance criteria:
- AC-3.1: `docs/runbook.md` has a `## Drafting run` section after `## Research run` whose steps name `cottonwood review --lead`, the `prepare-outreach` skill, `cottonwood record-run --skill prepare-outreach`, `cottonwood approve draft`, `cottonwood prepare-send` and `cottonwood log-outreach`.

### US-4 — Checks
Acceptance criteria:
- AC-4.1: `uv run pytest`, `uv run ruff check .`, `uv run mypy .` and `uv run ruff format --check .` all pass.

## Constraints & assumptions
- The export carries no email address: the skill drafts the message body, and the founder addresses it in their own client; contact data stays in `contacts` and `suppression` (R-35, R-27).
- The skill reads a file the developer exported (`review --lead ID --json --out out/leads/ID.json`) rather than running the CLI: skills have no shell (architecture decision 6).
- An undraftable lead (suppressed, or no contact email) still exports with exit 0 so the skill can see why; `prepare-send` remains the enforcing gate.
- Claim status in the export is the effective status (`claims.effective_statuses`); `prepare-send` recomputes it and never trusts the claims list.

## Success metrics
- The phase-5 exit criterion for this feature holds: the `prepare-outreach` skill outputs a draft, a claims list and a brief, and skips suppressed contacts (roadmap phase 5).
