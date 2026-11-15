# Assumptions — scaffold

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** Which Python version should the package target?
- **Answer:** Python 3.12, pinned in .python-version, requires-python >=3.12
- **Why:** Spec asks for a current Python 3; 3.12 is installed through uv and is supported by every tool in the stack.

## A-2 · plan
- **Question:** Flat or src layout, and which build backend?
- **Answer:** Flat layout with cottonwood/ at the repo root, built with hatchling
- **Why:** architecture.md's tree puts cottonwood/ at the root; hatchling handles a flat package with one line of config.

## A-3 · plan
- **Question:** How does an 'empty versioned SQLite file' get its version?
- **Answer:** Ship db/migrations/001_baseline.sql with no tables; migrate sets user_version 1; data-core adds tables as 002_*.sql
- **Why:** The roadmap exit criterion needs a versioned yet empty file; a no-op baseline migration gives that without creating data-core's tables early.

## A-4 · plan
- **Question:** Where does the database file live by default?
- **Answer:** data/cottonwood.db, overridable with COTTONWOOD_DB or --db; data/ is git-ignored
- **Why:** Contact data must stay out of git (architecture privacy NFR); config/pilot.yaml does not exist yet.

## A-5 · plan
- **Question:** How do uv commands run inside the Claude Code Bash sandbox, which cannot write ~/.cache/uv?
- **Answer:** Set [tool.uv] cache-dir = ".uv-cache" in pyproject.toml and git-ignore it
- **Why:** Observed: uv fails with 'Operation not permitted' on ~/.cache/uv inside the sandbox; a repo-local cache keeps the checks runnable there.

## A-6 · plan
- **Question:** How strict should lint and typecheck be?
- **Answer:** mypy strict over cottonwood and tests; ruff rules E, F, I, B, UP with line length 100
- **Why:** Starting strict on an empty codebase costs nothing and keeps later features honest.

## A-7 · do
- **Question:** uv panics inside the Claude Code Bash sandbox (system-configuration NULL object) for any networked command, including plain `uv run`; how are the AC commands run?
- **Answer:** Run `uv run ...` outside the sandbox for checks and verification; `UV_OFFLINE=1 UV_NO_SYNC=1 uv run ...` works inside it. The repo-local cache-dir stays.
- **Why:** Observed in this build: plain uv run exits 101 in the sandbox, the offline form works. The settings file is write-denied, so the fix (sandbox exclusion for uv) is the user's call.

## A-8 · fix
- **Question:** sir fix apply for F-correctness-6 committed the deletion of db/migrations/001_baseline.sql but left the new cottonwood/migrations/001_baseline.sql untracked; how does it get into the branch?
- **Answer:** Leave it for the ship stage's sir ship commit, and confirm the file is in the pushed branch before the PR is marked ready.
- **Why:** Build guardrails forbid committing by hand; without the file a clean checkout has no baseline migration and CI would fail, so ship must carry it.
