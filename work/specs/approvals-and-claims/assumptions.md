# Assumptions — approvals-and-claims

Questions this build answered itself with a recommendation (`sir build assume`): stage, question, answer, and why.

## A-1 · plan
- **Question:** Which feature builds the R-24 `suppress` command: approvals-and-claims or send-gate?
- **Answer:** approvals-and-claims builds `suppress EMAIL --reason TEXT [--source TEXT]`; send-gate's log-reply opt_out reuses its insert.
- **Why:** architecture.md puts suppress in gate.py with approve and claims, the phase-5 exit criterion lists `suppress works without a lead` separately from the send gate, and send-gate needs it to exist first.

## A-2 · plan
- **Question:** R-19 says a claim becomes verified only through a founder claim approval, but the claims file is hand-edited YAML: how is that enforced?
- **Answer:** A claim's effective status is verified only when config/claims.yaml marks it verified AND an unvoided claim_verified activity (written by `approve claim ID`) has the same verified_by and verified_at; `cottonwood claims` prints effective statuses and exits 1 naming every mismatch. The CLI never rewrites the YAML.
- **Why:** Architecture decision 5 keeps claims in a reviewed, diffable YAML file; rewriting it from code would drop comments, and trusting either side alone would let a hand edit or a stray approval verify a claim.

## A-3 · plan
- **Question:** How does a draft approval identify the draft, so send-gate (R-21: an approval covers the lead and that draft) can tell it is the same draft?
- **Answer:** `approve draft PATH --lead N` requires the lead and an existing file, and stores the path and the SHA-256 of the file's bytes in the approval payload.
- **Why:** A path alone would let an edited draft pass as approved; the digest is cheap, deterministic and needs no new table.

## A-4 · do
- **Question:** Main's credential scan (tests/test_no_send_credentials.py, CCGE-113) fails after the research-skill merge because sir task contracts and specs under work/ quote the sample credential strings as acceptance-criterion text. How should it be fixed?
- **Answer:** Exempt the work/ tree (sir planning records: task contracts, specs, todo) from the repository scan, as the test already exempts its own file; every other tracked file is still scanned. Carried by CCGE-118 through task allow-test because its pytest criterion cannot pass otherwise.
- **Why:** work/ holds requirement text about credentials, never configuration the app reads; rewriting archived contracts would alter the audit record, and loosening the matcher would weaken it for real config files.
