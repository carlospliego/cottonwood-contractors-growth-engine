# Cottonwood Growth Engine — verification

Outcomes are numbered as in `project.md`. Thresholds come from the spec (`docs/cottonwood-growth-engine.md`). Where the founder hasn't set a number yet, the row says so.

## How we will know each outcome is met (metric, source, threshold)
| # | Outcome | Metric | Source | Threshold |
|---|---|---|---|---|
| 1 | Inbound captured | Labeled test form inquiry and labeled test phone inquiry visible in the `review` file sent to the founder | `out/review-*.md` plus the R-4 runbook checklist row results | Both present and labeled; every R-4 checklist item has `checked_at`, a result and an owner |
| 2 | Evidence-backed prospects | Hand-review results per motion; newest-evidence age per lead | `report` (hand-review counts, data-quality failures); `review` (evidence age) | 0 `fabricated`; every reviewed lead within the configured max evidence age; false-positive rate within the founder's Gate 1 threshold (*number open: founder*) |
| 3 | Gated outreach loop | Sends, gate violations, replies by type, handoffs | `report` | ≥ 1 send prepared by `prepare-send` and logged, 0 gate violations, every reply followed by a `handoff` event. Or, if sending is blocked, the report names the blocking open question |
| 4 | Honest reporting | R-28 metric coverage | `report --period 30d` checked against the R-28 list | Every R-28 line present; zeros print as `0`; KPI shows `n/a` at 0 hours; estimated values labeled |
| 5 | Within budget | Monthly recurring cost; developer and founder hours | `log-cost`, `agent_runs` cost, `log-time` | ≤ $500/month in total; model cost ≤ the founder's monthly cap (*amount open: founder*); founder sales time ≤ 10 h/week; developer ≤ 20 h/week |
| 6 | Market signal | KPI = (qualified direct + partner conversations) ÷ founder hours | `report --period 30d` | None. Reported as is, zero included |

**Founder gates** (run in parallel with the builds; the developer records each sign-off with `approve` once the commands exist):
| Gate | Passes when | Who decides | If it fails |
|---|---|---|---|
| G0 Truth | R-4 checklist complete; week-1 open questions (GA4/privacy, Formspark, response capacity) answered | Founder with developer | Fix the inbound path first; nothing else depends on it in software |
| G1 Evidence | First sample hand-reviewed: ≥ 5 per available motion, 0 `fabricated`, false-positive rate within threshold | Founder | Revise sources or the research-skill instructions; re-sample |
| G2 Contact | Every "before first send" open question answered; claims verified; sender identity and postal address configured; reply relay confirmed; restore rehearsed | Founder | Sends stay blocked; research and founder introductions continue; the report states the blocker |
| G3 Repeatability | Two consecutive weekly reports with 0 gate violations and all opt-outs logged the same day | Founder with developer | Fix the step that broke before adding volume |

## Test & rollout strategy (environments, flags, canaries)
- **Tests:** every feature ships pytest tests on labeled synthetic fixtures (`tests/fixtures/`, every record marked `FIXTURE-`). Each `prepare-send` refusal reason, each suppression check point and each R-n behavior has at least one test. Tests never touch the network, the live site or Formspark.
- **Checks:** `pytest`, `ruff check`, `ruff format --check` and `mypy` run through sir's configured checks on every build.
- **Environments:** one real database (`data/cottonwood.sqlite`) plus a scratch database for rehearsals (`COTTONWOOD_DB=data/scratch.sqlite`). Live verification of the website, Formspark and the inbox is a founder checklist item, not a test.
- **Rollout:** each phase merges as its own PR, in roadmap order. Real data enters only after phase 2 merges, and only labeled test inquiries come first. Real prospects enter after phase 4. The first real send waits for phase 5 and Gate 2.
- **Canary:**
  - The first real send goes to a single approved recipient.
  - Before any second send, the developer confirms the full loop: prepared draft, logged send, and a reply relayed to the developer or no reply after the founder's chosen wait.
  - The developer also rehearses an opt-out on a test address the founder controls.
- **Skill runs:** each run is recorded with its cost. Spend against the monthly cap is checked in each weekly report.

## Rollback plan
- **Code:** each feature is one PR. Revert that PR's merge commit. Migrations are additive, so a schema rollback means restoring the pre-merge backup by following the runbook restore procedure.
- **Data:** take a `backup` before every migration, before each import of real records, and daily during active use. Restore by following the runbook, which sets the current database aside first.
- **Outreach:** to stop all sending, the founder stops sending prepared drafts. No automated path exists that could keep sending. Opt-outs and suppression are never rolled back: restoring an older backup is followed by re-applying the suppression entries logged since, which the runbook lists.
- **Skills:** to stop all Claude runs, the developer stops starting them. A bad skill version is reverted with its PR, and any records it imported are voided with `correction` events.
- **Inbound:** the existing Formspark form and its email notifications remain the fallback record throughout. No phase changes them.
