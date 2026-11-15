# Cottonwood Growth Engine — runbook

Step-by-step procedures for the founder and developer. Commands run from the repository root.
The live database is `data/cottonwood.db` (or `$COTTONWOOD_DB`), and backups go to
`data/backups/` (`paths.backup_dir` in `config/pilot.yaml`). Everything under `data/` is
git-ignored (R-34). The SQL below uses the `sqlite3` command-line shell; any SQLite client works.

Later features add the inbound checklist and relay sections to this file.

## Restore from backup

Use this when the live database is lost, damaged or wrong (R-33). There is no restore command:
the steps are deliberately manual, and each one keeps a copy of what it replaces.

1. If the live database still opens, take a fresh backup of it first:
   `uv run cottonwood backup`
2. Set the current database aside so nothing is lost. Use the current UTC time in the name:
   `mv data/cottonwood.db data/cottonwood.db.before-restore-20261115T100000Z`
3. Copy the chosen backup into place (backups are named `cottonwood-YYYYMMDDTHHMMSSZ.db`,
   in UTC, with `-2`, `-3` … for more than one in the same second):
   `cp data/backups/cottonwood-20261114T090000Z.db data/cottonwood.db`
4. Check that the restored file opens and is intact. This must print `ok`:
   `sqlite3 data/cottonwood.db 'PRAGMA integrity_check;'`
5. Check that it contains the suppression table. This must print a number, not an error:
   `sqlite3 data/cottonwood.db 'SELECT count(*) FROM suppression;'`
6. Bring the restored file up to the current schema (an older backup is upgraded; a current
   one reports `applied 0`):
   `uv run cottonwood migrate`
7. Re-apply the suppression entries added after the backup was taken, as in the next section.
   Do not skip this: an opt-out recorded after the backup must still be honoured (R-24).

If step 4 or 5 fails, put the set-aside file back (`mv` it to `data/cottonwood.db`) and try an
older backup.

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
SELECT count(*) AS missing FROM before_restore.suppression
    WHERE email_norm NOT IN (SELECT email_norm FROM main.suppression);
DETACH DATABASE before_restore;
```

`INSERT OR IGNORE` skips an address that is already suppressed, so running it twice is safe.
Do not use `INSERT OR REPLACE` to change an entry: an existing suppression row is never
replaced (the insert is silently skipped and the old row stays). If `missing` is not 0 (an
entry was added before the backup but is not in it), drop the `WHERE` line and run the block
again; copying every row is also safe for the same reason.

Keep the set-aside file until you are sure the restore is good, then delete it. It holds
contact data, so never copy it outside `data/`.

## Deletion requests

When a person asks to have their data deleted (R-35):

1. Take a backup first: `uv run cottonwood backup`.
2. Find the contact: `SELECT id, name, email, email_norm FROM contacts WHERE email_norm =
   'jane@example.com';` (lower-case, trimmed address).
3. Make sure the address is suppressed **before** clearing it, so they are never contacted
   again. This keeps an existing entry and adds one if there is none:

   ```sql
   INSERT OR IGNORE INTO suppression (email_norm, reason, source, added_at)
       VALUES ('jane@example.com', 'deletion_request', 'founder', '2026-11-15T10:00:00Z');
   ```

4. Clear the contact's personal fields and set `deleted_at` (the row stays, so leads and
   activities that point at it remain valid):

   ```sql
   UPDATE contacts
   SET name = NULL, email = NULL, email_norm = NULL, phone_e164 = NULL, role = NULL,
       source_url = NULL, deleted_at = '2026-11-15T10:00:00Z'
   WHERE id = 42;
   ```

5. Clear personal notes about them in their leads' free-text fields (`hypothesis`,
   `next_action`, `property_location`) with an `UPDATE leads … WHERE contact_id = 42`.
6. Activities are append-only (R-17): past activity payloads cannot be edited or deleted. Record
   the request as a new activity instead, with no personal details in it:

   ```sql
   INSERT INTO activities (contact_id, type, payload, actor, occurred_at, recorded_at)
       VALUES (42, 'correction', '{"reason": "deletion_request"}', 'founder',
               '2026-11-15T10:00:00Z', '2026-11-15T10:00:00Z');
   ```

   Notes already written into earlier activity payloads stay in the database. This is a known
   gap between R-35 ("remove … notes") and R-17 (append-only); tell the person if it applies.
7. **Keep the suppression entry.** It is never deleted (R-24), even on a deletion request: it is
   what stops the address from being imported or contacted again.

Backups taken before the request still hold the old fields until those backup files are
deleted; nothing removes them automatically, so say so if the person asks.
