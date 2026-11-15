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

## Done

- [x] `CCGE-002` — Migrations runner and migrate command → [CCGE-002.md](done/CCGE-002.md)
- [x] `CCGE-001` — Python package, tooling and CLI skeleton → [CCGE-001.md](done/CCGE-001.md)
