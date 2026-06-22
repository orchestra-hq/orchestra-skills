---
name: identify-pipeline-error
description: >
  The entry point for fixing anything in an Orchestra pipeline. Use this skill FIRST whenever a
  user wants to fix, debug, retry, or understand a failed Orchestra pipeline — e.g. "fix my
  pipeline", "what's broken", "why did my pipeline fail", "debug this run", "retry it" — or pastes
  an Orchestra run URL, a UUID, a pipeline name/alias, an error message, or a Slack/alert message.
  This skill does NOT fix anything itself beyond a few categories. It GETs the pipeline run and the
  task runs, identifies which task failed, its integration, and the cause, then HANDS OFF to the
  right fixer: a Python task code issue → fix-pipeline-python-task; a dbt task code/config issue →
  fix-pipeline-dbt-task; an Orchestra-platform/configuration issue → fix-orchestra-pipeline. All
  other causes (data quality, vendor/ingestion, auth, network, timeout/infra, upstream, and other
  integrations) are handled here.
---

# Identify Pipeline Error

The router. **Identify** which task broke and **why**, then **route** to the skill that fixes it.
This skill draws a clean line: it *identifies and classifies*; the `fix-*` skills *fix*. Do not
attempt code repairs, schema changes, or branch validation here — that is the fixer's job.

Narrate each step briefly, like a data engineer. Never print secrets/tokens.

## 0. Access

MCP is preferred but optional. If the Orchestra MCP tools aren't present, use the public REST API
with `$ORCHESTRA_API_KEY` (check the env — it's often already set). If neither MCP nor a key is
available, point the user at the Orchestra MCP setup docs (https://docs.getorchestra.io/docs/mcp)
or ask for an API key, then stop.

- MCP: `list_pipeline_runs`, `list_task_runs`, `list_operations`, `list_task_run_logs`,
  `download_task_run_log`, `list_task_run_artifacts`, `list_pipelines` — see
  `../../references/orchestra/mcp/tools-quick-ref.md`.
- REST base: `https://app.getorchestra.io/api/engine/public` — header
  `Authorization: Bearer $ORCHESTRA_API_KEY`.

## 1. Parse the input → get an ID

The user may give you several forms. Extract the IDs before doing anything else.

- **Orchestra URL** — pull UUIDs from the path:
  ```
  https://app.getorchestra.io/pipeline-runs/{pipeline_run_id}
  https://app.getorchestra.io/pipeline-runs/{pipeline_run_id}/task-runs/{task_run_id}
  https://app.getorchestra.io/pipelines/{pipeline_id}/runs/{pipeline_run_id}
  https://app.getorchestra.io/pipelines/{pipeline_id}
  ```
  Self-hosted instances use the same path structure on a different domain.
- **Bare UUID** — try it as a pipeline run ID first (`list_pipeline_runs` /
  `GET /pipeline_runs?pipeline_run_ids=<id>`). If nothing comes back, treat it as a pipeline ID and
  look up its recent runs.
- **Pipeline name / alias** — match with `list_pipelines`, then find its latest FAILED run.
- **"What's broken" with no ID** — `list_pipeline_runs` with `status=FAILED`, default last 7 days.
  If several pipelines failed, present a one-line-per-pipeline triage table and ask which to take.
- **Error text / Slack alert** — extract the pipeline/task names and find the run; the pasted error
  is evidence you'll use in Step 4, but still fetch the run so the fixer has IDs to work with.

## 2. GET the pipeline run

```
list_pipeline_runs(pipeline_run_ids=<RID>)        # MCP
GET /pipeline_runs?pipeline_run_ids=<RID>          # REST
```
Capture: `id` (RID), `pipelineId` (PID), `pipelineName`, `status`, `message`, `branch`, `commit`,
`envName`, `triggeredBy`. The run's `branch` is where the **Orchestra YAML** lives (not necessarily
the code branch).

**Feature-branch guard:** if the failure is on a non-`main` branch from a `MANUAL` trigger while
scheduled/main runs are green, this is likely mid-development, not an incident. Confirm with the
user before going further (see `../../references/orchestra/pipeline/diagnosis-patterns.md` →
FEATURE_BRANCH_RUN).

## 3. GET the task runs → find the one that broke

```
list_task_runs(pipeline_ids=<PID>, status=FAILED)   # also pull status=WARNING for context
GET /task_runs?pipeline_ids=<PID>&page_size=50       # REST: filter to this RID client-side
```
Gotcha: `pipeline_run_ids` does **not** filter `/task_runs` over REST — filter by `pipelineRunId`
yourself. `/task_runs` returns a 7-day window.

Identify the **first** FAILED task (downstream FAILED/SKIPPED tasks are usually symptoms of it).
Capture, for that task:
- `integration` (e.g. `PYTHON`, `DBT_CORE`, `SNOWFLAKE`, `HTTP`, `FIVETRAN`, `AIRBYTE_*`)
- `integrationJob`, `taskName`, `taskId`, `id` (TRID)
- `message`, `externalStatus`, `externalMessage`, `numberOfAttempts`
- `taskParameters`, `runParameters`, `connectionId`

Pull just enough evidence to classify — the failed task's messages, and if the integration alone
doesn't decide it, a quick look at logs/artifacts:
```
list_task_run_logs(<RID>, <TRID>)  →  download_task_run_log(... range_header="bytes=-262144")
list_task_run_artifacts(<RID>, <TRID>)   # dbt: run_results.json is the tell for data-test fails
```
Don't deep-dive here. Reading full logs, reproducing locally, and downloading every artifact is the
**fixer's** job — gather only what you need to route correctly.

## 4. Identify the cause and ROUTE

Classify using the failed task's integration + messages + minimal evidence, cross-referenced with
`../../references/orchestra/pipeline/diagnosis-patterns.md`. Then route:

| Cause you identified | Route to |
|---|---|
| **Python task — code / dependency / destination-schema issue** (`integration=PYTHON`; traceback, `ModuleNotFoundError`, bad logic, script writes a shape the destination rejects) | **invoke `fix-pipeline-python-task`** |
| **dbt task — code / config issue** (`DBT_CORE`; compilation error, bad `ref`/`source`, SQL identifier, missing column, `profiles.yml`/target error) | **invoke `fix-pipeline-dbt-task`** |
| **Orchestra-platform / configuration issue** (pipeline YAML misconfig, wrong/missing task inputs, task ordering, env/connection wiring, a transient Orchestra-side blip needing a plain retry, or an Orchestra-backed pipeline needing `update_pipeline`) | **invoke `fix-orchestra-pipeline`** |
| **Any other cause** (see §5) | **handle here** |

State the routing decision in one line before handing off, e.g.:
> Identified: the dbt task `transform_core` failed with a compilation error — an issue with the dbt
> task **code**. Handing off to `fix-pipeline-dbt-task`.

Pass the fixer everything it needs so it doesn't re-identify: **RID, PID, failed TRID, integration,
`taskParameters` (verbatim), branch/commit, and your cause classification.** If the fixer later
discovers the category was wrong (e.g. a "dbt code" failure is really a data-quality test failure),
it hands back here.

## 5. Causes this skill handles itself

These aren't python-code, dbt-code, or Orchestra-config problems, so there's no `fix-*` skill to
call. Identify precisely, then report with the right next action — **don't edit code or data, and
don't retry data-writing tasks without the user's OK.**

- **Data quality** — dbt/Snowflake DQ test failure, schema drift, unexpected nulls/dupes. Report
  the failing test and counts (`run_results.json`). Decide *with the user*: legitimate data issue
  (notify the data owner, don't touch the data) vs. an overly strict threshold (they may adjust it).
- **Source freshness** (`ERROR STALE`) — an upstream source hasn't refreshed. Point at the ingestion
  task/pipeline that feeds it; this is usually a data/upstream issue, not code.
- **Vendor / ingestion** (Fivetran, Airbyte, Estuary, dbt Cloud, and similar managed integrations) —
  surface `platformLink` and `connectionId`/connector id and tell the user what to fix in that
  product's UI. Do not open a Git PR. "Sync already running" → increase the schedule interval.
- **Auth** (`401/403`, expired/rotated creds, insufficient privileges) — name the `connectionId` to
  update and give the exact `GRANT`/IAM change. User action.
- **Network / firewall** (connection refused, DNS, "request timed out") — give the Orchestra IPs to
  whitelist / private-connection guidance. User action.
- **Timeout / infra** — a safe, idempotent task (a query, a test) can be retried with a heads-up;
  otherwise suggest bumping compute or the timeout, and confirm before retrying a data-writing task.
- **Upstream** (source API down, empty extract) — summarise; usually can't be fixed from here.
- **Other integrations** (`SNOWFLAKE` query errors, `HTTP` non-2xx, AWS/Azure/GCP jobs) — diagnose
  with `diagnosis-patterns.md`. If the failure is misconfiguration in version-controlled pipeline
  YAML, that's an Orchestra-config issue → route to `fix-orchestra-pipeline` instead. If it's a SQL
  bug in a repo, treat it as a code fix and open a PR per `fix-orchestra-pipeline` Step 5.

Read `../../references/orchestra/pipeline/diagnosis-patterns.md` for per-integration signals and
`../../references/orchestra/pipeline/remediation-playbooks.md` for the recommended action.

## 6. Output

When routing, keep it to the handoff line (§4) plus the IDs you're passing on.

When handling a cause yourself (§5), present a compact diagnosis and a recommendation:

```
## Diagnosis: `<pipeline name>`
- **Failed task:** `<task name>` (`<INTEGRATION>` / `<integrationJob>`)
- **Cause:** <one specific sentence — which object/test/credential/endpoint, not just "error">
- **Category:** DATA / VENDOR / AUTH / NETWORK / TIMEOUT / UPSTREAM / …
- **Evidence:** <quoted log line or external message; which operation failed>
- **Confidence:** High / Medium / Low

**Recommended next step:** <one line — who does what, with the exact GRANT/IP/UI path if relevant>
```

## Notes

- This skill identifies and routes; it never repairs code, mutates schemas, or runs branch
  validation — those belong to the `fix-*` skills.
- Always hand the fixer the IDs and `taskParameters` so it doesn't repeat identification.
- Diagnose the **first** failed task; skipped downstream tasks are symptoms.
- Never expose secrets from logs. Mind the 7-day metadata window; batch `list_*` calls.
- Confirm before retrying anything that writes data, especially in Production.
