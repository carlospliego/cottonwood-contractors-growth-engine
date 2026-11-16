# Lessons

Reviewed, long-term lessons for this repo. Added only through `/sir:retro` after human approval.
Sections are keyed by path glob (or `general`); the session-start hook loads sections that match the active task.

## general

## tests/**
- 2026-11-15: A sir fix regression test's first line is `# sir-target: tests/NEW_FILE.py`, naming the new test file itself, never the source file; that file must not exist yet. (source: review 20261115-191126)
- 2026-11-15: Fix-author test commands are `PYTHONPATH=. UV_OFFLINE=1 UV_NO_SYNC=1 uv run pytest -q tests/FILE.py`; without PYTHONPATH the mutant trial tests the main checkout's editable install, not the trial copy. (source: CCGE-063)
