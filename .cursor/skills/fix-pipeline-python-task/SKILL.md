---
name: fix-pipeline-python-task
description: >
  Diagnose and fix Python tasks running in Orchestra Pipelines. Succinct,
  API-first. Biased toward editing the script and re-running until it works,
  with additive-only schema changes to the destination.
disable-model-invocation: true
---

Diagnose → locate the script → check what it lands → fix → validate → confirm → merge/save. Narrate each step briefly, like a data engineer. Never print secrets/tokens.

## 0. Access

MCP is preferred but optional. If the Orchestra MCP tools aren't present, use the public REST API with `$ORCHESTRA_API_KEY` (check the env — often already set). For git, `$GITHUB_TOKEN` is usually set. For schema checks you also need a **warehouse credential** (Snowflake/BigQuery) or **S3/object-store credential** — ask the user if not present.
If neither MCP nor an Orchestra key is available, read `../../../references/orchestra/mcp/setup.md` and stop.

Base: `https://app.getorchestra.io/api/engine/public` — header `Authorization: Bearer $ORCHESTRA_API_KEY`.

## 1. Establish the failure (from a run ID / URL)

```
GET /pipeline_runs?pipeline_run_ids=<RID>          # run status, pipelineId, branch, commit
GET /task_runs?pipeline_ids=<PID>&page_size=50     # find the FAILED task; filter results by pipelineRunId yourself
```
Gotchas: `pipeline_run_ids` does **not** filter `/task_runs` — filter client-side. 7-day window.

**Capture `taskParameters` exactly** — `command`/`entrypoint`, `python_version`, `package_manager`, `requirements`, `branch`, `project_dir`, and any env/run inputs. Preserve them on every retry. The pipeline run's `branch` is where the *Orchestra YAML* lives; the script's source branch (if git-backed) is a separate task param.

Logs:
```
GET /pipeline_runs/<RID>/task_runs/<TRID>/logs                                # list filenames
GET /pipeline_runs/<RID>/task_runs/<TRID>/logs/download?filename=<file>       # URL-encode spaces
```
Read the Python traceback bottom-up: the last exception line is the real error, not the first.

## 2. Classify the cause

1. **Script code** (bad logic, wrong column/key, unhandled None, API change) → fix the script. **Most common.**
2. **Dependency / env** (missing/incompatible package, wrong `python_version`) → fix `requirements`/version, re-run.
3. **Data / schema mismatch** — the script writes a shape the destination rejects (new/renamed column, type change, NOT NULL, missing table). → see §3–4. **Very common for Python tasks.**
4. **Infra/timeout/memory** → bump compute / retry.
5. **Upstream** (source API down, empty extract) → summarise; often can't fix from here.

## 3. Locate the script — it may NOT be in git

Python tasks come in two shapes; handle both:
- **Git-backed** (`branch` + `project_dir` + a file/entrypoint): clone and reproduce locally.
  ```bash
  git clone --depth 1 -b <branch> https://x-access-token:$GITHUB_TOKEN@github.com/<org>/<repo>.git
  cd <repo>/<project_dir> && pip install -r requirements.txt
  python <entrypoint>        # reproduce; iterate edit → run
  ```
- **Inline / not git-controlled** (script lives in the Orchestra pipeline definition, or is generated). Then there's no repo to PR. Get the script body from the pipeline definition (MCP `get`/`list_pipelines`, or the Orchestra YAML if it's stored in git). You'll fix it **in the pipeline definition** (Orchestra-backed → `update_pipeline`; or edit the inline `command`). State clearly to the user that this script isn't version-controlled and recommend they back it into git so it can be PR'd and CI-tested.

Either way: **heavy bias toward making it actually run.** Edit → execute → read the next error → repeat, exactly like fixing layered dbt bugs. Don't declare it unfixable after one error; the first traceback usually masks the next.

## 4. Check what lands — verify the destination schema

Python tasks almost always drop data into a warehouse or S3. Before and after a fix, confirm the *actual landed shape* rather than trusting the script's intent.

- **Warehouse** (with a credential):
  ```sql
  SELECT column_name, data_type FROM <db>.INFORMATION_SCHEMA.COLUMNS
  WHERE table_schema='<SCHEMA>' AND table_name='<TABLE>';     -- or DESCRIBE TABLE
  SELECT COUNT(*) FROM <db>.<schema>.<table>;                  -- did rows actually land?
  ```
- **S3 / object store**: list the target prefix, read one object's header/schema (parquet metadata or CSV header), confirm partition path and that new files appeared with the run timestamp.

Compare the columns/types the script writes against what's there. A schema-mismatch failure is the signal to evolve the destination — additively.

### Additive-only rule (important)
Bias **strongly** toward upward-compatible schema changes; never destroy data or shape:
- ✅ `ALTER TABLE ... ADD COLUMN` for a new field; widen a type (e.g. `INT`→`NUMBER`, `VARCHAR(50)`→`VARCHAR(200)`); add a new partition/prefix.
- ✅ Make the script tolerant: select/write columns explicitly, default missing values, append rather than overwrite.
- ❌ No `DROP`/`DELETE`/`TRUNCATE`, no renaming/removing columns, no narrowing types, no recreating the table to "fix" it.
- If a fix genuinely requires a destructive change, **stop and ask** — present it as the last option with the exact DDL, don't apply it.

## 5. Fix, then validate before trusting prod

1. **Git-backed:** new branch off the script's branch, commit each fix clearly, open a PR. **Inline/non-git:** apply via `update_pipeline` (Orchestra-backed) or edit the inline command; tell the user it's not version-controlled.
2. Trigger a validation run (against the fix branch if branch is a run input; else against the corrected definition):
   ```
   POST /pipelines/<PID>/start
   { "branch": "<yaml-branch>",
     "continueDownstreamRun": true,
     "runInputs": { ... preserve original params ... } }
   ```
3. **Run the whole pipeline, not just the Python task.** Python is usually the *first* step of `python → dbt → reverse-ETL/BI` — the data it lands is what every downstream task consumes. A full `/start` (no `taskIds`) runs the entire DAG top-to-bottom — prefer it, because it proves dbt and downstream actually accept the new output. If you target just the failed task (`"taskIds": ["<TID>"]`) or use `"retryFromFailed": true`, you **must** also send `"continueDownstreamRun": true`, or the load succeeds in isolation while dbt/BI never re-run — and a schema change you just made (§4) goes unverified downstream.
4. **Writes are not free.** Python tasks mutate the warehouse/S3. Prefer a dev/staging target or a scratch schema if one exists. If it's **Production**, get the user's OK first **unless** they've said to proceed. Watch for non-idempotent appends (re-running may duplicate rows) — confirm the write is truncate-load or upsert before repeated retries, or clean up test rows.

## 6. Poll, loop, confirm

Poll `GET /pipeline_runs?pipeline_run_ids=<RID>` ~every 20s, one line per check:
```
▶ Run e2049b86 — RUNNING (0:42)
✅ Run e2049b86 — SUCCEEDED (1:44)
```
A very-fast `SUCCEEDED` can be a stale first read — re-check `completedAt`/`message`. On failure, diagnose the new error (getting *further* is progress) and loop to §3.

**Confirm the whole pipeline, not just the Python task.** "Fixed" means the *pipeline run* is `SUCCEEDED` with every task green — list its task runs (`GET /task_runs?pipeline_ids=<PID>` filtered to the RID) and confirm none are `FAILED`. The most common trap: the Python load goes green but the downstream **dbt** task fails because it didn't expect the new/changed column — that's exactly why you run downstream (and why schema changes must be additive, §4). Then **also verify the data landed** (§4: row count > 0, expected columns present) — a Python task can exit 0 yet write nothing. When green end-to-end, merge the PR (or finalise the inline fix), and re-run with the original params to prove the real config works.

## 7. Summary

```
## Fixed: <pipeline name>
- Final run: <id> — SUCCEEDED
- Root cause: <one line>
- Fixes: <script change(s); any additive schema change with the DDL>
- Data check: <table/prefix — N rows, columns confirmed>
- PR / definition: <link or "inline, not version-controlled — recommend backing to git">
```

## Notes
- Preserve task parameters on every retry.
- Validate end-to-end: full `/start` by default; for targeted/`retryFromFailed` retries always add `"continueDownstreamRun": true`, and confirm every task in the run is green — a Python fix isn't done until the downstream dbt/BI tasks accept its output.
- Additive schema changes only; never drop/delete/narrow without explicit approval.
- Confirm before writing to Production unless told to proceed; mind append-duplication.
- Inline scripts can't be PR'd or CI-tested — always recommend version-controlling them.
- Only Orchestra-backed pipelines use `update_pipeline`; GitHub-backed need repo commits.
