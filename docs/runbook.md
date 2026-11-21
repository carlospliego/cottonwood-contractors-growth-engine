# Cottonwood Growth Engine — runbook

Step-by-step procedures for the founder and developer. Commands run from the repository root.
The live database is `data/cottonwood.db` (or `$COTTONWOOD_DB`), and backups go to
`data/backups/` (`paths.backup_dir` in `config/pilot.yaml`). Everything under `data/` is
git-ignored (R-34). The SQL below uses the `sqlite3` command-line shell; any SQLite client works.

## Restore from backup

Use this when the live database is lost, damaged or wrong (R-33). There is no restore command:
the steps are deliberately manual, and each one keeps a copy of what it replaces.

A crash in the middle of a write can leave a `data/cottonwood.db-journal` (or `-wal` and
`-shm`) file next to the database. SQLite applies that file to whatever database next opens
under the live name, so it must never be left behind for the backup to pick up.

1. If the live database still opens, take a fresh backup of it first:
   `uv run cottonwood backup`
2. Let SQLite finish or undo any write that was cut off, using the database's own journal.
   Open the live database once (skip this if the file does not open at all):
   `sqlite3 data/cottonwood.db 'SELECT count(*) FROM sqlite_master;'`
3. Set the current database aside so nothing is lost, together with any `-journal`, `-wal` or
   `-shm` file next to it, all under the same new name. Use the current UTC time in the name:
   `mv data/cottonwood.db data/cottonwood.db.before-restore-20261115T100000Z`
   and then, for each of these files that exists:
   `mv data/cottonwood.db-journal data/cottonwood.db.before-restore-20261115T100000Z-journal`
   `mv data/cottonwood.db-wal data/cottonwood.db.before-restore-20261115T100000Z-wal`
   `mv data/cottonwood.db-shm data/cottonwood.db.before-restore-20261115T100000Z-shm`
4. Check that nothing is left under the live name. This must list no files (the shell reports
   "no matches found" or "No such file or directory"); if it lists any, move them as in step 3:
   `ls data/cottonwood.db-*`
5. Copy the chosen backup into place (backups are named `cottonwood-YYYYMMDDTHHMMSSZ.db`,
   in UTC, with `-2`, `-3` … for more than one in the same second):
   `cp data/backups/cottonwood-20261114T090000Z.db data/cottonwood.db`
6. Check that the restored file opens and is intact. This must print `ok`:
   `sqlite3 data/cottonwood.db 'PRAGMA integrity_check;'`
7. Check that it contains the suppression table. This must print a number, not an error:
   `sqlite3 data/cottonwood.db 'SELECT count(*) FROM suppression;'`
8. Bring the restored file up to the current schema (an older backup is upgraded; a current
   one reports `applied 0`):
   `uv run cottonwood migrate`
9. Re-apply the suppression entries added after the backup was taken, as in the next section.
   Do not skip this: an opt-out recorded after the backup must still be honoured (R-24).

If step 6 or 7 fails, put the set-aside file back (`mv` it to `data/cottonwood.db`, and any
set-aside `-journal`, `-wal` or `-shm` file to the matching `data/cottonwood.db-` name) and try
an older backup.

## Re-applying suppression after a restore

Suppression entries are never deleted (R-24), so every entry in the set-aside database must
also be in the restored one. Copy across the rows added after the backup was taken. The cutoff
is the backup's time stamp written as UTC ISO-8601: `cottonwood-20261114T090000Z.db` becomes
`2026-11-14T09:00:00Z`.

Open the restored database with `sqlite3 data/cottonwood.db` and run, with your file name and
cutoff:

```sql
ATTACH DATABASE 'data/cottonwood.db.before-restore-20261115T100000Z' AS before_restore;
INSERT OR IGNORE INTO suppression (email_norm, reason, source, added_at)
    SELECT email_norm, reason, source, added_at
    FROM before_restore.suppression
    WHERE added_at > '2026-11-14T09:00:00Z';
SELECT changes() AS reapplied;
-- Must print 0: no set-aside entry may be missing from the restored database.
-- A set-aside row with a NULL or empty key also counts as missing.
SELECT count(*) AS missing FROM before_restore.suppression AS b
    WHERE b.email_norm IS NULL OR b.email_norm = ''
        OR NOT EXISTS (SELECT 1 FROM main.suppression AS m WHERE m.email_norm = b.email_norm);
DETACH DATABASE before_restore;
```

`INSERT OR IGNORE` skips an address that is already suppressed, so running it twice is safe.
Do not use `INSERT OR REPLACE` to change an entry: an existing suppression row is never
replaced (the insert is silently skipped and the old row stays). If `missing` is not 0 (an
entry was added before the backup but is not in it), drop the `WHERE` line and run the block
again; copying every row is also safe for the same reason. A row with a NULL or empty
`email_norm` cannot be copied (the column requires an address): find it with
`SELECT * FROM before_restore.suppression WHERE email_norm IS NULL OR email_norm = '';` and
add the right address by hand.

Keep the set-aside file until you are sure the restore is good, then delete it. It holds
contact data, so never copy it outside `data/`.

## Deletion requests

When a person asks to have their data deleted (R-35):

1. Take a backup first: `uv run cottonwood backup`.
2. Find the contact: `SELECT id, name, email, email_norm FROM contacts WHERE email_norm =
   'jane@example.com';` (lower-case, trimmed address).
3. Run the request for that contact id: `uv run cottonwood deletion-request --contact 42`
   (`--actor` defaults to `founder`). It prints what it changed, for example
   `contact 42 deleted: personal fields cleared, 2 activity record(s) redacted, kept the
   existing suppression of jane@example.com; recorded as activity 311`. An unknown id is
   refused and changes nothing.

In one transaction the command:

- makes sure the address is suppressed **before** clearing it, so they are never contacted
  again (an existing entry is kept as it is; one is added with reason `deletion_request` if
  there is none);
- clears the contact's personal fields and sets `deleted_at` (the row stays, so leads and
  activities that point at it remain valid), as this SQL would:

  ```sql
  UPDATE contacts
  SET name = NULL, email = NULL, email_norm = NULL, phone_e164 = NULL, role = NULL,
      source_url = NULL, address = NULL, deleted_at = '2026-11-15T10:00:00Z'
  WHERE id = 42;
  ```

- clears what they told us in their leads: the free-text fields (`hypothesis`,
  `next_action`, `property_location`, and the `project_scope` log-inbound records) and a
  budget they stated themselves (`value_basis` `buyer-stated`), as this SQL would:

  ```sql
  UPDATE leads
  SET hypothesis = NULL, next_action = NULL, property_location = NULL, project_scope = NULL
  WHERE contact_id = 42;
  UPDATE leads
  SET value_amount = NULL, value_basis = NULL
  WHERE contact_id = 42 AND value_basis = 'buyer-stated';
  ```

  A value we estimated ourselves (any other basis) is not something they told us and stays;
- removes their details from activity records: the one exception to append-only activities
  (R-17). In every activity of the contact or its leads, the `note` and `need` payload values
  are cleared and any other occurrence of their name, email or phone becomes `[removed]`. No
  activity is deleted, and the append-only trigger is back in place when the command ends;
- records the removal as a new `deletion_request` activity whose payload holds only the
  reason and how many activity records were redacted.

**Keep the suppression entry.** It is never deleted (R-24), even on a deletion request: it is
what stops the address from being imported or contacted again.

Backups taken before the request still hold the old fields until those backup files are
deleted; nothing removes them automatically, so say so if the person asks.

## Inbound verification checklist

Work through this list in week 1, before Gate 0 is signed off (R-4). For each item fill in
`checked_at` (America/Denver date and time), `result` (what you saw, pass or fail) and `owner`
(who checked it, or who owns the open question). Leave nothing blank at sign-off; an item that
cannot pass yet says so in `result`.

| Item | checked_at | result | owner |
|---|---|---|---|
| Labeled commercial test submission through the live website form |  |  |  |
| Labeled residential test submission through the live website form |  |  |  |
| Spam/blocked-submission path (what Formspark does with a blocked or spam-flagged submission, and where it shows up) |  |  |  |
| Notification spam-folder check (the Formspark notification is not landing in spam) |  |  |  |
| Formspark account owner, plan, limits and submission retention |  |  |  |
| Auto-forward to the developer of Formspark notifications and outreach-mailbox replies |  |  |  |
| Mobile form and phone-link check (the form submits and the phone link dials on a phone) |  |  |  |
| Missed-call handling and owner (who returns missed calls, and by when) |  |  |  |
| Same-working-day response capacity (the founder can meet the site's same-day promise) |  |  |  |
| GA4 vs privacy-page reconciliation (is GA4 deployed, and does the privacy page match) |  |  |  |

Logging the two test submissions (mark them `--test` so they are labeled and never counted):

    uv run cottonwood log-inbound --channel form --received "2026-11-16 09:30" --segment commercial --name "Checklist test (commercial)" --email developer-test@example.com --test
    uv run cottonwood log-inbound --channel form --received "2026-11-16 09:40" --segment residential --name "Checklist test (residential)" --email developer-test@example.com --test --confirm-duplicate

The second one uses the same address on the same day, so it needs `--confirm-duplicate` (see
Relay below). Then run `uv run cottonwood review --out out/review.md` and check that both rows
carry the `TEST` label and that the count line says `Test inquiries excluded: 2`. Log the labeled
test phone inquiry the same way with `--channel phone --test`.

## Relay

The developer operates the tool, but the founder owns the inbox and the phone, so inquiries reach
the developer by relay:

- Formspark notifications and replies to the outreach mailbox are auto-forwarded (or CC'd) to
  the developer.
- The founder sends a daily note covering calls (answered and missed) and in-person events.
- Everything relayed is logged the same working day it arrives, and opt-outs the same day.

Logging a relayed form inquiry (only the fields the inquirer gave; leave scope and budget out
unless they stated them, R-1):

    uv run cottonwood log-inbound --channel form --received "2026-11-16 09:30" --segment commercial --name "Pat Lee" --email pat@example.com --company "Acme Holdings" --scope "lobby refresh"

Logging a phone inquiry from the founder's daily note (`--segment unknown` if they did not say):

    uv run cottonwood log-inbound --channel phone --received "2026-11-16 14:05" --segment unknown --phone "(801) 555-0134"

`--received` is when the inquiry arrived, not when you log it: `YYYY-MM-DD HH:MM` in America/Denver
time, or UTC ending in `Z`. Add `--test` for the checklist's test submissions.

If the email or phone matches an inquiry already logged on the same America/Denver date, the
command stops with a warning such as `warning: possible duplicate of lead(s) 12 received
2026-11-16` (R-2). If it is the same person following up, do not log it again. If it really is
a separate inquiry, re-run with `--confirm-duplicate` (or answer `y` at the prompt). Without
either, it refuses with exit 1 and saves nothing.

Opt-outs are suppressed the same day they arrive (R-24). Until the `suppress` command exists,
add the entry directly; an address already suppressed is kept as it is. `email_norm` must be
the trimmed, lower-cased address, or the suppression will not match the contact; let SQLite do
it by pasting the address as written into `lower(trim(...))`:

```sql
INSERT OR IGNORE INTO suppression (email_norm, reason, source, added_at)
    VALUES (lower(trim(' Pat@Example.com ')), 'opt_out', 'relay', '2026-11-16T21:05:00Z');
```

Send the founder the review after logging: `uv run cottonwood review --out out/review.md`. The
file holds contact data; `out/` is git-ignored, so keep it there.

## Research run

Run this each time the `research-prospects` skill researches a brief (R-25, R-26). The skill can only write a file; the CLI decides what is imported, and the founder hand-reviews a sample before Gate 1.

1. In Claude Code, start the `research-prospects` skill with a research brief (motion, geography, firm types, how many), or run `/research-prospects demand [COUNT]` to have it scan current demand in the territory, pick the strongest opportunity and research that. A demand run also writes `out/research/YYYY-MM-DD-SLUG.demand.md`, which explains the pick; the founder reads it before the import. Note the start time.
2. When it has written `out/research/YYYY-MM-DD-SLUG.json`, note the end time.
3. Check the file without writing anything: `cottonwood prospects-import out/research/YYYY-MM-DD-SLUG.json --check`. Note `passed` when it ends `0 rejected`, else `failed`. Never repair a rejected record by guessing: drop it or research it again.
4. Import it: `cottonwood prospects-import out/research/YYYY-MM-DD-SLUG.json`.
5. Run `/cost` in the same Claude Code session and note the total cost and tokens.
6. Record the run: `cottonwood record-run --skill research-prospects --skill-version VERSION --model MODEL --started "YYYY-MM-DD HH:MM" --ended "YYYY-MM-DD HH:MM" --input "brief: ..." --output out/research/YYYY-MM-DD-SLUG.json --validation passed --tokens N --cost USD --cost-source claude-code-cost`. `VERSION` is the `version` in the skill's frontmatter.
7. When the cost is not exact (for example read from the billing console for a period), use `--cost-source billing-console --estimated` instead. On a subscription plan where `/cost` shows no dollar figure, leave out `--cost` and `--cost-source`, and `--tokens` too when no token count is shown: `--tokens` and `--cost` may be left out when no figure is available, and the run is recorded with them stored as unknown, never as 0.
8. Hand-review a sample with `cottonwood review` and `cottonwood mark-reviewed` (Gate 1).

## Drafting run

Run this for each lead the founder wants contacted (R-20, R-21, R-22, R-26). The skill only writes files; the founder approves the exact draft in writing, `prepare-send` makes the only sendable copy, and the founder sends it from their own mail client.

1. Export the lead: `cottonwood review --lead ID --json --out out/leads/ID.json`. If the export says `"draftable": false`, stop: `blocked_by` names why (`suppressed`, `no_contact_email`).
2. In Claude Code, start the `prepare-outreach` skill on `out/leads/ID.json`. Note the start time.
3. When it has written `out/drafts/ID-N.md`, `out/drafts/ID-N.claims.json` and `out/briefs/ID-N.md`, note the end time. If it wrote nothing, it reports why; do not draft by hand around it.
4. Run `/cost` in the same Claude Code session and note the total cost and tokens.
5. Record the run: `cottonwood record-run --skill prepare-outreach --skill-version VERSION --model MODEL --started "YYYY-MM-DD HH:MM" --ended "YYYY-MM-DD HH:MM" --input out/leads/ID.json --output out/drafts/ID-N.md --validation passed --tokens N --cost USD --cost-source claude-code-cost`. Use `--validation failed` when the claims list does not validate or the brief flags a claim that is not verified. On a subscription plan where `/cost` shows no dollar figure, leave out `--cost` and `--cost-source`, and `--tokens` too when no token count is shown: `--tokens` and `--cost` may be left out when no figure is available.
6. Send the founder the brief and the draft. Any claim the brief flags must be approved first (`cottonwood approve claim CLAIM-ID ...`) or dropped from the draft.
7. When the founder approves the exact draft in writing, record it: `cottonwood approve lead ID --approver NAME --reference "..."` (once per lead) and `cottonwood approve draft out/drafts/ID-N.md --lead ID --approver NAME --reference "email YYYY-MM-DD Re: SUBJECT"`. Any later edit to the draft needs a new approval.
8. Make the sendable copy: `cottonwood prepare-send ID out/drafts/ID-N.md`. On a refusal, fix what each `refused:` line names; never edit `out/send/` by hand.
9. The founder sends `out/send/ID-N.md` from their own mail client to the contact's address.
10. Log the send with the prepared id that `prepare-send` printed: `cottonwood log-outreach ID --prepared P --recipient ADDRESS --source-url URL --message out/send/ID-N.md --sender NAME --date YYYY-MM-DD`. A `gate violation:` line means the send bypassed the gate; report it to the founder the same day.
11. Log each reply as it arrives: `cottonwood log-reply ID TYPE` (an opt-out suppresses the address, a bounce makes the contact ineligible).
