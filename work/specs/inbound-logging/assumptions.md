# Assumptions — inbound-logging

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** Where are an inquiry's project scope and budget stored? The leads table has no scope column.
- **Answer:** A new migration 003_inbound.sql adds a nullable leads.project_scope column; a stated budget goes in leads.value_amount (exact decimal text) with value_basis 'buyer-stated'. Both stay NULL unless the inquirer stated them.
- **Why:** Putting scope in the append-only inquiry_logged payload would make it impossible to clear on a deletion request (R-35); R-9 already defines buyer-stated money with a basis.

## A-2 · plan
- **Question:** How does log-inbound take the received time?
- **Answer:** A required --received option accepting America/Denver local 'YYYY-MM-DD HH:MM' or a UTC ISO-8601 timestamp ending in Z; it is stored as UTC (R-32). There is no default to 'now'.
- **Why:** Inquiries are often logged hours after they arrive via the relay; a silent default to the logging time would corrupt same-day duplicate checks and acknowledgement timing.

## A-3 · plan
- **Question:** What counts as 'explicit confirmation' for a duplicate inquiry (R-2)?
- **Answer:** On a duplicate the command prints a warning naming each matching lead; on an interactive terminal it asks 'Save anyway? [y/N]' and saves only on y/yes; the --confirm-duplicate flag confirms non-interactively. Without a TTY and without the flag it refuses (exit 1) and writes nothing.
- **Why:** Keeps the check usable both by hand and from scripts while making the default safe: nothing is saved without a deliberate yes.

## A-4 · plan
- **Question:** Which existing records does the duplicate check compare against?
- **Answer:** Every inbound_inquiry lead (test inquiries included) whose contact's email_norm or phone_e164 equals the new inquiry's normalized email or E.164 phone and whose received_at falls on the same America/Denver date.
- **Why:** R-2 names exactly these keys and the local date; including tests lets the labeled test submissions exercise the check.

## A-5 · plan
- **Question:** Do inquiries reuse existing contacts and organizations?
- **Answer:** Each inquiry creates its own contact row holding only the supplied name, email (plus email_norm) and phone; a supplied --company reuses an organization with the same name_norm or creates one. Contacts are not merged across inquiries.
- **Why:** R-1 says to record only what the inquirer supplied; merging contacts would mix fields from different submissions. Contact matching rules (R-7) belong to prospect-import.

## A-6 · plan
- **Question:** How much of `review` does this feature build, and what does 'excluded from counts' mean before `report` exists?
- **Answer:** `review` prints (or writes with --out PATH, creating parent folders) a Markdown inbound-inquiries section: a count line by channel and segment that excludes test inquiries and states how many tests were left out, then one row per inquiry with tests labeled TEST. The direct-candidate and relationship-prospect queues (R-13 checklist, ordering) come with prospect-review; a shared non-test filter in the review module is what report will reuse.
- **Why:** The roadmap gives R-13's candidate queues to phase 4 and only R-31 for review to phase 2; the phase exit needs tests labeled in review and excluded from counts.

## A-7 · plan
- **Question:** What input does log-inbound require and how are bad values handled?
- **Answer:** Required: --channel form|phone, --received, --segment commercial|residential|unknown, and at least one of --name, --email, --phone. Invalid email, phone, budget decimal, time or choice refuses with exit 1 (argparse choice errors exit 2) naming the field, and writes nothing. The inquiry_logged activity payload holds no personal data: channel, segment, is_test and any confirmed duplicate lead ids.
- **Why:** An inquiry nobody can be contacted or identified by is useless; keeping personal data out of append-only payloads keeps deletion requests (R-35) workable.

## A-8 · do CCGE-028
- **Question:** Which version-dependent tests change, and what does log-inbound do with a missing or unmigrated database?
- **Answer:** Every version-dependent assertion in tests/test_migrate.py, tests/test_schema.py and tests/test_runbook_restore.py moves to version 3 (including the version-1 upgrade test and the packaged-migration list). log-inbound catches db.MigrationError and sqlite3.Error, prints 'error: ...' and exits 1; it never migrates on its own.
- **Why:** Surveyor's recommendation; those files are already the task's tests_to_change, and auto-migrating would hide a stale database.

## A-9 · do CCGE-028
- **Question:** How are budget values, blank options and UTC --received values normalized?
- **Answer:** Budget: reject non-finite and negative decimals, store str(Decimal) and turn -0 into 0. Blank or whitespace-only text options are stripped and treated as not supplied (NULL). A UTC --received goes through parse_utc then to_utc_iso, so stored values are always second-precision Z.
- **Why:** Surveyor's recommendation; keeps R-1's 'only supplied fields' honest (no empty strings) and stored timestamps uniform.

## A-10 · do CCGE-028
- **Question:** The runbook's deletion-request step lists lead free-text fields to clear but not the new leads.project_scope; CCGE-031 keeps that section unchanged. What now?
- **Answer:** CCGE-028 does not touch the runbook; a follow-up task is filed to add project_scope (and value_amount/value_basis from inbound budgets) to the deletion-request clearing step.
- **Why:** Surveyor's recommendation; keeps each task within its contract while making sure the R-35 gap is tracked.

## A-11 · do CCGE-028
- **Question:** tests/test_backup.py also asserts the schema version (2) of backup copies at lines 63, 113 and 176, but it was not in the task's tests to change. Change it?
- **Answer:** Yes: only its version literal moves from 2 to 3; the backup behavior it checks is unchanged. Recorded in the CCGE-028 receipt as an edit outside the listed tests.
- **Why:** The survey missed the file; the assertion checks that a backup copies the live schema, which is now version 3, so updating the literal keeps the test's intent.

## A-12 · do CCGE-029
- **Question:** Duplicate-check details: does a 'yes' at the prompt record duplicate_of, how are EOF/Ctrl-C handled, what does the warning show, and what about NULL keys or times and --confirm-duplicate without a match?
- **Answer:** A y/yes answer records duplicate_of exactly like --confirm-duplicate. EOF or KeyboardInterrupt at the prompt counts as no (exit 1, nothing written). The warning lists the matching lead ids ascending, comma-separated, and the shared America/Denver date as YYYY-MM-DD. Leads with NULL received_at and inquiries with neither email nor phone never match. --confirm-duplicate without a match saves normally with duplicate_of [] and no warning.
- **Why:** Surveyor's recommendations; both answers are explicit confirmations, and the defaults keep nothing saved without a deliberate yes.

## A-13 · do CCGE-030
- **Question:** review details: generated time, output identity, filter name, ordering, escaping, failures and deleted contacts?
- **Answer:** The handler takes utc_now() once and passes it to render_review(conn, generated_at), whose text ends in one newline and is written identically to stdout and to --out. The non-test filter is COUNTED_LEADS_FILTER = 'is_test = 0' (the contract's name; plan.md said counted_inquiries_filter). Rows sort by received_at DESC, then id DESC. Cells escape backslash and pipe and turn line breaks into spaces; NULL or empty prints '—'. A missing database, an SQLite error or a write error exits 1 with 'error: ...', and the review is rendered before any folder is created. A deleted contact's lead shows its remaining stored values as-is (CCGE-032 clears scope and budget).
- **Why:** Surveyor's recommendations; they keep the output deterministic and testable and leave nothing written on failure.

## A-14 · do CCGE-031
- **Question:** Runbook layout: where do the new sections go, what shape is the checklist, how is a same-day opt-out recorded before an opt-out command exists, and does Relay show the duplicate warning?
- **Answer:** Both sections are appended after Deletion requests so the existing sections stay byte-identical. The checklist is a table 'Item | checked_at | result | owner' with one row per R-4 item and blank cells to fill in. Relay states opt-outs are suppressed the same day and gives an INSERT OR IGNORE INTO suppression SQL block until the suppress command (send-gate feature) exists; no command is invented. Relay shows the exact duplicate warning and says to use --confirm-duplicate only for a genuinely separate inquiry.
- **Why:** Surveyor's recommendations; they keep existing runbook tests valid and document only commands that exist.
