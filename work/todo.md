# Todo

Index of tasks. Each entry links to its contract in `tasks/`. Managed by `/sir:task`; do not renumber.

## Open

- [ ] `CCGE-003` — Verify each migration's transaction and version bump after it runs → [CCGE-003.md](tasks/CCGE-003.md)
- [ ] `CCGE-004` — Reject a migration numbered 000 with a specific message → [CCGE-004.md](tasks/CCGE-004.md)
- [ ] `CCGE-005` — Report already-committed migrations when a later one fails → [CCGE-005.md](tasks/CCGE-005.md)
- [ ] `CCGE-006` — Tie usage-error exits to EXIT_USAGE and drop the unreachable string branch → [CCGE-006.md](tasks/CCGE-006.md)
- [ ] `CCGE-007` — Document that migration files must not contain transaction control → [CCGE-007.md](tasks/CCGE-007.md)
- [ ] `CCGE-008` — Test the unreadable-migration and rollback branches of _apply → [CCGE-008.md](tasks/CCGE-008.md)
- [ ] `CCGE-009` — Refuse a database newer than the known migrations → [CCGE-009.md](tasks/CCGE-009.md)
- [x] `CCGE-010` — UTC time and contact normalization helpers → [CCGE-010.md](tasks/CCGE-010.md)
- [x] `CCGE-011` — Core schema migration with append-only triggers → [CCGE-011.md](tasks/CCGE-011.md)
- [x] `CCGE-012` — Config loader and backup command → [CCGE-012.md](tasks/CCGE-012.md)
- [x] `CCGE-013` — Runbook: restore and deletion-request procedures → [CCGE-013.md](tasks/CCGE-013.md)
- [ ] `CCGE-014` — Backup to an unwritable folder exits 1 instead of a traceback → [CCGE-014.md](tasks/CCGE-014.md)
- [ ] `CCGE-015` — Non-UTF-8 config file raises ConfigError → [CCGE-015.md](tasks/CCGE-015.md)
- [ ] `CCGE-016` — normalize_name keeps word boundaries at hyphens → [CCGE-016.md](tasks/CCGE-016.md)
- [ ] `CCGE-017` — normalize_domain strips www. only when a dotted host remains → [CCGE-017.md](tasks/CCGE-017.md)
- [ ] `CCGE-018` — display_local formats offsets with seconds correctly → [CCGE-018.md](tasks/CCGE-018.md)
- [ ] `CCGE-019` — paths.backup_dir expands ~ and trims spaces → [CCGE-019.md](tasks/CCGE-019.md)
- [ ] `CCGE-020` — One DatabaseMissingError shared by db and backup → [CCGE-020.md](tasks/CCGE-020.md)
- [ ] `CCGE-021` — db.connect raises a general DatabaseError, not MigrationError → [CCGE-021.md](tasks/CCGE-021.md)
- [ ] `CCGE-022` — Email whitespace error message names the real problem → [CCGE-022.md](tasks/CCGE-022.md)
- [ ] `CCGE-023` — Test load_config fallback and empty-value branches → [CCGE-023.md](tasks/CCGE-023.md)
- [ ] `CCGE-024` — Test the default config/pilot.yaml path → [CCGE-024.md](tasks/CCGE-024.md)
- [ ] `CCGE-025` — Deletion-section order check fails when the backup step is missing → [CCGE-025.md](tasks/CCGE-025.md)
- [ ] `CCGE-026` — Test the international phone length bounds → [CCGE-026.md](tasks/CCGE-026.md)
- [ ] `CCGE-027` — Test email whitespace rejection and domain userinfo stripping → [CCGE-027.md](tasks/CCGE-027.md)

## Done

- [x] `CCGE-002` — Migrations runner and migrate command → [CCGE-002.md](done/CCGE-002.md)
- [x] `CCGE-001` — Python package, tooling and CLI skeleton → [CCGE-001.md](done/CCGE-001.md)
