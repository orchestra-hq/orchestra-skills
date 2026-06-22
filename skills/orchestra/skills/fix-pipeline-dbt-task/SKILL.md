---
name: fix-pipeline-dbt-task
description: >
  Diagnose and fix dbt Core jobs running in Orchestra Pipelines. Succinct,
  API-first workflow refined from real fixes.
---

Diagnose → fix → validate on a branch → confirm → merge. Narrate each step briefly, like a data engineer. Never print secrets/tokens.

## 0. Access

MCP is preferred but optional. If the Orchestra MCP tools aren't present, use the public REST API directly with `$ORCHESTRA_API_KEY` (check the env — it's often already set). For git, `$GITHUB_TOKEN` is usually set too.
If neither MCP nor a key is available, read `../../../references/orchestra/mcp/setup.md` and stop.

Base: `https://app.getorchestra.io/api/engine/public` — header `Authorization: Bearer $ORCHESTRA_API_KEY`.

## 1. Establish the failure (from a run ID / URL)

```
GET /pipeline_runs?pipeline_run_ids=<RID>          # run status, pipelineId, branch, commit
GET /task_runs?pipeline_ids=<PID>&page_size=50     # find FAILED task; then filter results by pipelineRunId yourself
```
Gotchas: the `pipeline_run_ids` filter does **not** work on `/task_runs` — filter client-side. `/task_runs` returns a 7-day window.

**Capture `taskParameters` exactly** — especially `branch`, `commands`, `project_dir`, `use_state_orchestration`. These are run inputs you must preserve on retry. Note the pipeline run's `branch` is where the *Orchestra YAML* lives; the dbt clone branch is a separate task param (commonly an input like `dbt_branch`).

Logs:
```
GET /pipeline_runs/<RID>/task_runs/<TRID>/logs                                  # list filenames
GET /pipeline_runs/<RID>/task_runs/<TRID>/logs/download?filename=1/debug_task   # URL-encode spaces, e.g. 1/dbt%20run
```
`debug_task` = `dbt debug` (config/YAML validation); `dbt run` / `dbt build` = compile + execution.

## 2. Classify the cause

1. **Data** (DQ test / source freshness fails) → leave, notify owner, or adjust threshold. Don't edit data.
2. **dbt code** (YAML syntax, bad `ref`/`source`, SQL identifier, missing column) → fix in repo. **Most common.**
3. **Infra/timeout** → retry / bump compute.
4. **Orchestra pipeline** --> fix ORchestra Pipeline if it is git-backed. Otherwise tell user to edit Orchestra pipeline.
5. **upstream ingestion** → summarise; you usually can't fix from here.

Source-freshness `ERROR STALE` lines are category 1 (data), not code — they rarely fail a `dbt run`; don't chase them unless they're the terminal error.

## 3. The reported error is usually just the FIRST bug

A failed dbt run reports one error; broken branches often hide several layered behind it. Don't fix-one-and-retry blindly — reproduce locally and clear them in one branch:

```bash
git clone --depth 1 -b <dbt_branch> https://x-access-token:$GITHUB_TOKEN@github.com/<org>/<repo>.git
cd <repo>/<project_dir>
export DBT_PROFILES_DIR=$PWD            # write a dummy snowflake profiles.yml; parse never connects
pip install -q dbt-<adapter>
dbt parse --no-version-check            # catches YAML + ref/source + compilation errors offline
```
`dbt parse` finds YAML and `ref`/`source` errors with no warehouse. Runtime SQL errors (e.g. `invalid identifier`) only surface on an actual `dbt run` — so expect to iterate steps 3–5.

**Fixing strategy:** typos (`ref('customersdfdfd_clean')`→`customers_clean`, `site_nadfdfdme`→`site_name`) fix in place. For damage beyond a typo (missing `*,` passthrough, dropped commas, mangled blocks), **diff against a known-good branch (usually `main`, which builds green) and restore that file** rather than guessing the intended logic.

## 4. Fix on a branch, validate before prod

1. New branch off the failed dbt branch; commit each fix with a clear message. Open a PR (git-backed pipelines can only be fixed via repo; check `storageProvider`). Never label a code fix "user action" — open the PR.
2. **Validate without merging** if the pipeline exposes branch/command inputs — trigger against the fix branch:
```
POST /pipelines/<PID>/start
{ "branch": "<yaml-branch, e.g. main>",
  "continueDownstreamRun": true,
  "runInputs": { "dbt_branch": "<fix-branch>", "dbt_command": "run" } }
```
If branch isn't an input, tell the user it can't be hotfixed until they parameterise it (add `inputs.dbt_branch`) — don't guess.
3. **Run the whole pipeline, not just the dbt task.** A real ETL flow is `python → dbt → reverse-ETL/BI`; dbt is rarely the last step. A full `/start` (no `taskIds`) runs the entire DAG top-to-bottom — prefer it. If you instead target the failed task (`"taskIds": ["<TID>"]`) or use `"retryFromFailed": true` to skip an expensive upstream, you **must** also send `"continueDownstreamRun": true`, or every task after the fixed one is skipped and the pipeline only *looks* fixed. Targeted retries also assume the fixed task's upstream inputs already exist — if not, do a full run.
4. `dbt run` / `build` materialises tables. If the env is **Production**, get the user's OK first **unless** they've said to proceed. Then it's their call.

## 5. Poll, loop, confirm

Poll `GET /pipeline_runs?pipeline_run_ids=<RID>` ~every 20s, one line per check:
```
▶ Run e2049b86 — RUNNING (0:42)
✅ Run e2049b86 — SUCCEEDED (1:44)
```
A very-fast `SUCCEEDED` can be a stale first read — re-check `completedAt`/`message` before trusting it. On failure, immediately diagnose the new error (it's progress if the run got *further*) and loop to step 3.

**Confirm the whole pipeline, not just the dbt task.** "Fixed" means the *pipeline run* is `SUCCEEDED` with every task green — not just that the dbt task passed. Check the run status, then list its task runs (`GET /task_runs?pipeline_ids=<PID>` filtered to the RID) and confirm none are `FAILED`. A downstream task (reverse-ETL, BI refresh, notification) can fail on the dbt output even when dbt itself is fine. When green end-to-end, merge the PR. As a last check, re-run with the **original** failing params to prove the real config is fixed.

## 6. Summary

```
## Fixed: <pipeline name>
- Final run: <id> — SUCCEEDED
- Root cause: <one line; note if reported error masked deeper bugs>
- Fixes: <table/list of file → bug → fix>
- PR: <link, merged>
```

## Notes
- Preserve task parameters on every retry.
- Validate end-to-end: full `/start` by default; for targeted/`retryFromFailed` retries always add `"continueDownstreamRun": true`, and confirm every task in the run is green.
- Confirm before retrying data-writing pipelines in Production unless told to proceed.
- Only Orchestra-backed pipelines use `update_pipeline`; GitHub-backed need repo commits.
- Batch `list_*` calls; mind the 7-day metadata window.
