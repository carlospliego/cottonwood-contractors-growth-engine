# Assumptions — research-skill

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** What values does record-run accept for validation and cost source, and how precise is the cost?
- **Answer:** validation passed|failed; cost source claude-code-cost|billing-console with an --estimated flag; cost a plain non-negative decimal with at most 4 places stored as exact text; tokens a non-negative whole number.
- **Why:** R-26 names Claude Code's /cost output and the billing console as the sources and requires an estimated mark; per-run model costs can be fractions of a cent, and the report already sums agent_runs.cost_usd as exact decimals.

## A-2 · plan
- **Question:** How does the developer get the validation result to record, given the skill has no Bash and cannot run the CLI (R-27)?
- **Answer:** Add prospects-import FILE --check: the same loader, validator and checklist keys as the import, the same rejection lines, a 'check: N valid, M rejected' summary, exit 1 on any rejection, and nothing written (no import_rejected activity).
- **Why:** R-25 requires Python validation before import; a check must not count as a data-quality failure, so it cannot reuse the import's write path.

## A-3 · plan
- **Question:** How is 'the skill produces a file that validates and imports' tested when tests cannot run Claude?
- **Answer:** The SKILL.md carries one fenced json worked example; a test extracts it, runs prospects-import --check and a real import against config/pilot.yaml's checklist keys, and other tests check the frontmatter tools allowlist, version and the stated rules.
- **Why:** Keeps the skill instructions and the schema from drifting apart, and checks R-27's tool restriction mechanically; a live run is the developer's Gate 1 step recorded with record-run.

## A-4 · plan
- **Question:** How is R-27's 'no email-sending credentials in the repository' checked?
- **Answer:** A pytest test scans every git-tracked text file for assignments to SMTP_PASS/SMTP_PASSWORD/SENDGRID_API_KEY/MAILGUN_API_KEY/POSTMARK_SERVER_TOKEN/SES_SECRET/MAIL_PASSWORD with a value and for smtp(s):// URLs with a password, naming file and line; .env itself is git-ignored and never read.
- **Why:** A deterministic check in the suite fails the PR if a credential is committed, without reading the local .env (denied by policy).
