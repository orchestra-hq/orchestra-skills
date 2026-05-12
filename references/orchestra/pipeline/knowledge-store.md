# Knowledge Store

This file is maintained by the Orchestra **pipeline** skills (`fix-orchestra-pipeline`, `triage-orchestra-pipeline`).
It records past pipeline fixes and discovered patterns — not MCP wiring or REST details (see `references/orchestra/README.md`).

## How this file works

Each time a pipeline is successfully fixed, a new entry is appended under "Fix history".
The skill reads this file during Step 4 (Diagnose) to check if similar errors have been
seen and resolved before. Over time, this builds a knowledge base specific to your
Orchestra workspace — your integrations, your common failure modes, your pipelines.

## Failure frequency profile

_This section is populated on first run by querying recent failed task runs across all
pipelines. It helps the skill prioritise which integration-specific patterns to check first._

**Last updated:** 2026-04-23

| Integration | Failure count (7d) | Most common error |
|-------------|-------------------|-------------------|
| DBT_CORE | 9 | requirements.txt file not found (matrix task failure) |
| AWS_BEDROCK | 5 | AccessDeniedException / ValidationException (model permissions, param errors) |
| DBT_CORE (dbt build) | 6 | dbt build --exclude source:atomic exit code 1 |
| PYTHON (dlt) | 3 | SQL operating on non-existent object |

## Fix history

_Entries are added here after each successful fix. Newest first._

## Fix: 2026-05-08 (session 4) — #fivetran #dbt #lightdash Failing Pipeline
- **Pipeline ID:** d1b9a7ce-ed16-4774-9378-ea3d950555fe
- **Environment:** Production
- **Error category:** DATA_ERROR
- **Integration:** DBT_CORE / DBT_CORE_EXECUTE
- **Integration job:** `dbt build --vars '{"orchestra_source_schema": "orchestra_metadata_app"}'`
- **Root cause:** Three separate schema layers each contained outdated `accepted_values` lists that didn't include new Orchestra enum values: `REUSED` (operationStatus), `REFRESH` (operationType), `CHART` (assetType). Each Fivetran sync pulls in the latest data; the accepted_values lists in all four files (source, staging, marts/dimensions, marts/facts) must stay in sync with the Orchestra API enum.
- **Fix applied:** PRs #74 and #75 — updated `models/staging/schema.yml`, `models/marts/dimensions/schema.yml`, and `models/marts/facts/schema.yml` to mirror the values already fixed in `models/schema.yml` (PRs #70–73). Run `54fdcb1b` SUCCEEDED.
- **Was auto-fixed?** Yes — PRs opened, merged, and pipeline triggered automatically.
- **First diagnosis correct?** Partially — identified the enum drift correctly, but discovered the dbt project has FOUR schema files with identical accepted_values lists (source, staging, marts/facts, marts/dimensions). Only the source was fixed in session 3; this session fixed the remaining three.
- **Notes:** ⚠️ FOUR-LAYER ACCEPTED_VALUES PATTERN — when Orchestra adds a new enum value, ALL FOUR schema files must be updated simultaneously: `models/schema.yml`, `models/staging/schema.yml`, `models/marts/facts/schema.yml`, `models/marts/dimensions/schema.yml`. Fixing one at a time causes successive pipeline failures as each layer gets tested in turn. Next time, grep the entire repo for the old value list and fix all occurrences in one PR: `grep -rn "MATERIALISATION" models/` will identify all files needing updates.

## Fix: 2026-05-05 (session 3) — #fivetran #dbt #lightdash Failing Pipeline
- **Pipeline ID:** d1b9a7ce-ed16-4774-9378-ea3d950555fe
- **Environment:** Production
- **Error category:** DATA_ERROR
- **Integration:** DBT_CORE / DBT_CORE_EXECUTE
- **Integration job:** `dbt build` on branch `broken-dbt`
- **Root cause:** Commit `e2b1c4f3` (PR #181) re-reverted the threshold fix AGAIN — `threshold: 2000` → `threshold: 0` in `dbt_projects/snowflake/models/clean/schema.yml`, causing `average_store_sales_example_sales__date__store__0` to fail with 57 results. This is the third recurrence of the same bug (previously fixed in PR #178 and #180).
- **Fix applied:** Opened PR #182 (`fix/restore-average-threshold-182` → `broken-dbt`) restoring `threshold: 2000`. Auto-triggered pipeline run `5f7fdb4b` on merge — SUCCEEDED.
- **Was auto-fixed?** Yes — PR opened, polled for merge, pipeline triggered automatically.
- **First diagnosis correct?** Yes — git history immediately revealed commit `e2b1c4f3` reverted `d8a4292` (the passing run's commit). Diagnosed from `list_task_runs` output alone without needing logs or artifacts.
- **Notes:** ⚠️ THIRD RECURRENCE — this pipeline is intentionally broken for demo purposes (pipeline name includes "Failing Pipeline"). The `broken-dbt` branch has a pattern of fix→revert→fix→revert cycles. Fastest path: check `git log --oneline` on `broken-dbt` and look for "Revert" commits. The fix is always `threshold: 2000` in `dbt_projects/snowflake/models/clean/schema.yml`. Expect this to recur.

## Fix: 2026-05-05 (session 2) — #fivetran #dbt #lightdash Failing Pipeline
- **Pipeline ID:** d1b9a7ce-ed16-4774-9378-ea3d950555fe
- **Environment:** Production
- **Error category:** CODE_ERROR
- **Integration:** DBT_CORE / DBT_CORE_EXECUTE
- **Integration job:** `dbt build` on branch `broken-dbt`
- **Root cause:** Commit `51e0d3a` on `broken-dbt` re-introduced `threshold: 0` in `dbt_projects/snowflake/models/clean/schema.yml`, causing `average_store_sales_example_sales__date__store__0` to fail with 57 results. PR #178 (prior session) had already fixed this exact bug; a new commit undid it.
- **Fix applied:** Opened PR #180 (`fix/average-test-threshold-broken-dbt` → `broken-dbt`) restoring `threshold: 2000`. Auto-triggered pipeline run `13287924` on merge — SUCCEEDED.
- **Was auto-fixed?** Yes — PR opened, polled for merge, pipeline triggered automatically.
- **First diagnosis correct?** Yes — git diff between passing commit `bdd3eb1` and failing commit `51e0d3a` immediately revealed the threshold change.
- **Notes:** ⚠️ RECURRING BUG — this is the second time `threshold: 0` has been committed to `broken-dbt`. If it recurs, the `broken-dbt` branch itself may be intentionally broken for demo purposes. Consider adding a CI check or dbt test guard. Fastest diagnosis path: `gh api repos/.../compare/{last_good_sha}...{failing_sha}` to diff the two commits directly — no need to pull logs or artifacts for this pattern.

## Fix: 2026-05-05 — #fivetran #dbt #lightdash Failing Pipeline
- **Pipeline ID:** d1b9a7ce-ed16-4774-9378-ea3d950555fe
- **Environment:** Production (inferred)
- **Error category:** CONFIG_ERROR
- **Integration:** DBT_CORE / DBT_CORE_EXECUTE
- **Integration job:** `dbt build` on branch `broken-dbt`
- **Root cause:** `threshold: 0` in `dbt_projects/snowflake/models/clean/schema.yml` on `broken-dbt` branch caused the `average` custom test on `store_sales_example` to compile to `WHERE avg_ > 0`, matching all 57 store/date rows. Test configured to fail if != 0 results. Correct value is `2000` (matches `main` branch).
- **Fix applied:** Opened PR #178 (`fix/average-test-threshold` → `broken-dbt`) changing `threshold: 0` → `threshold: 2000`. Auto-triggered pipeline rerun after merge. New run `70cb6b9e` succeeded.
- **Was auto-fixed?** Yes — PR opened, polled for merge, pipeline triggered automatically on merge.
- **First diagnosis correct?** Yes — compiled SQL in operation `externalDetail` field revealed the hardcoded `0` immediately.
- **Notes:** The previous run (85820e36) had failed with `pyproject.toml file not found` under UV package manager; that was fixed by switching to PIP before this session began. Always check the prior run's failure too — this pipeline had two distinct bugs on `broken-dbt`. The `externalDetail` field on FAILED operations contains the compiled SQL for dbt tests — use it to verify parameter substitution. Lightdash task was SKIPPED (not FAILED) because it has a condition gate on dbt success; don't count it as a separate failure.

## Investigation: 2026-04-23 — #bedrock
- **Pipeline ID:** 3bddc143-da37-45db-bf4c-7ccb10a384f3
- **Environment:** Production
- **Error category:** AUTH_FAILURE
- **Integration:** AWS_BEDROCK / AWS_BEDROCK_INVOKE_MODEL
- **Root cause:** IAM user `arn:aws:iam::381492077289:user/orchestra_user` lacked `bedrock:InvokeModel` permission for `amazon.nova-2-lite-v1:0` in `eu-west-1`. Pipeline had been manually retried 5+ times with identical failure.
- **Fix applied:** None — pipeline was deleted by user before fix was applied.
- **Was auto-fixed?** No
- **First diagnosis correct?** Yes — error message was explicit (AccessDeniedException 403)
- **Notes:** When you see repeated rapid manual retries (5+ in <5 min), it's almost always not a transient error. Check the connection/IAM before suggesting a retry. Model ID `amazon.nova-2-lite-v1:0` may not be a valid Bedrock model — worth flagging to user alongside the IAM fix.

## Investigation: 2026-04-23 — #snowflake #dlt #matrix
- **Pipeline ID:** 1c95fbce-71e2-44ec-b9d1-c4998d8fcb63
- **Environment:** Production
- **Error category:** CONFIG_ERROR (historical FAILED runs) → DATA_ERROR (current WARNING state)
- **Integration:** DBT_CORE / DBT_CORE_EXECUTE + PYTHON (dlt) + SNOWFLAKE
- **Root cause (FAILED, April 20):** dbt task failed with `requirements.txt file not found` despite the file existing at `dbt_projects/snowflake/requirements.txt` in `orchestra-hq/orchestra-blueprints`. Most recent run of the same date showed `Failed to start dbt Core task` with empty `runParameters` — task never dispatched. Root cause of why the file wasn't found despite existing is unresolved (likely a transient compute/clone issue).
- **Current state (April 22):** dbt now SUCCEEDS. Pipeline status is WARNING. Remaining warnings: (1) dlt loads report "no outputs were set" for all 3 matrix items (dbt_leads, social_leads, unstructured_feedback); (2) Snowflake Task objects `DBT_LEADS_TASK`, `SOCIAL_LEADS_TASK`, `UNSTRUCTURED_FEEDBACK_TASK` don't exist — expected, since dbt only recently started succeeding and hasn't created them yet; (3) `UNSTRUCTURED_FEEDBACK` table missing — suspect dlt load for that sheet is silently failing.
- **Fix applied:** None required — dbt issue self-resolved. Snowflake Task objects will be created on next successful dbt run. dlt/UNSTRUCTURED_FEEDBACK issue deferred by user.
- **Was auto-fixed?** N/A — issue had already resolved itself between April 20 and April 22
- **First diagnosis correct?** Partially — initial diagnosis was `requirements.txt missing` but the file exists. The real cause was likely transient. Updated on repo inspection.
- **Notes:** Always check the pipeline's `latestRunStatus` before diagnosing from historical FAILED runs — the issue may already be resolved. Git-backed pipelines: use `storageProvider` + `repository` + `yamlPath` fields to find and inspect the actual repo. This pipeline is `paused: true` — check if that's intentional before triggering retries. Snowflake Task objects created by dbt models will be absent until dbt runs successfully at least once; this is expected after a period of dbt failures.

## Fix: 2026-04-23 — #dbt #state #databricks
- **Pipeline ID:** 5e973cbe-47e5-46b9-b672-8301543fa382
- **Environment:** Production (inferred — pipeline has no named env in MCP response)
- **Error category:** PLATFORM_ERROR (transient — original logs unavailable, 9 days old)
- **Integration:** DBT_CORE / DBT_CORE_EXECUTE
- **Integration job:** DBT_CORE_EXECUTE (`dbt build` with state orchestration)
- **Root cause:** Original failure from 2026-04-14 could not be diagnosed from retained metadata/logs (7-day window). Likely a transient Databricks connectivity or cluster startup issue. Pipeline had not been retried in 9 days.
- **Fix applied:** Triggered a fresh pipeline run via `start_pipeline`. Run succeeded on first attempt (task: "dbt run state", 8.5 min). Connection: `dbt_databricks_78961`. Repo: `orchestra-hq/test-data-dbt-databricks` @ `main`.
- **Was auto-fixed?** Yes — retry resolved the issue
- **First diagnosis correct?** N/A — original error data unavailable due to 7-day retention
- **Notes:** Log/task run data is typically only available for the last ~7 days. For failures older than 7 days, trigger a fresh run and diagnose from the new run's data. The `use_state_orchestration: true` parameter means dbt uses `--state` to skip unchanged models — retry is generally safe for this pattern.

<!-- TEMPLATE (do not delete):
## Fix: YYYY-MM-DD — [Pipeline Name]
- **Pipeline ID:** [id]
- **Environment:** [env]
- **Error category:** [AUTH_FAILURE | TIMEOUT | QUERY_ERROR | RESOURCE_CONFLICT | NETWORK_ERROR | CONFIG_ERROR | DEPENDENCY_FAILURE | PLATFORM_ERROR | CODE_ERROR | RATE_LIMIT | DATA_ERROR]
- **Integration:** [integration type]
- **Integration job:** [job type]
- **Root cause:** [specific description of what went wrong]
- **Fix applied:** [exact action taken]
- **Was auto-fixed?** [yes/no — did the skill fix it or did the user need to act?]
- **First diagnosis correct?** [yes/no]
- **Notes:** [anything useful for future reference]
-->
