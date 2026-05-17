---
name: fix-orchestra-pipeline
description: >
  Automatically diagnose and fix failed Orchestra data pipelines. Use this skill whenever a user
  mentions Orchestra pipeline failures, broken pipelines, pipeline errors, task failures, pipeline
  debugging, or wants to understand why an Orchestra pipeline run failed. Also trigger when the user
  says things like "fix my pipeline", "what's broken", "why did my pipeline fail", "debug this run",
  "retry my pipeline", or references Orchestra pipeline runs, task runs, or pipeline errors.
  This skill handles the full lifecycle: identify failures, fetch logs and artifacts, diagnose the
  root cause, apply fixes where possible, retry, and learn from past fixes. It supports all
  Orchestra integrations including dbt, Snowflake, Python, HTTP, Fivetran, Airbyte, and more.
  Trigger this skill even if the user just pastes an Orchestra error message, pipeline run URL,
  pipeline run link from the Orchestra UI, a UUID, a Slack alert, or a pipeline name/alias.
---

# Fix Orchestra Pipeline

Diagnose, fix, and retry failed Orchestra pipelines — then learn from every fix.

## Prerequisites

This skill requires the **Orchestra MCP server** to be connected. If it is not connected,
**read `../../references/orchestra/mcp/setup.md`**
and follow the setup steps with the user before proceeding.

The Orchestra API key must be configured in the MCP server. All MCP calls are scoped to the
user's workspace.

## MCP-first policy (single exception)

Use Orchestra MCP tools for all operations in this skill. Argument summaries: `../../references/orchestra/mcp/tools-quick-ref.md`.

The only allowed direct Orchestra REST call is **reading pipeline YAML** when needed and MCP
cannot return the full definition. Details: `../../references/orchestra/api/rest-pipeline-yaml.md`.

Do not use direct REST calls for listing runs, logs, artifacts, operations, retrying runs,
or updating pipelines.

## Parsing user input

The user may provide their problem in several forms. Parse the input before entering the
workflow:

### Orchestra URLs
Users often paste a link from the Orchestra UI. Extract IDs from any of these URL patterns:

```
https://app.getorchestra.io/pipeline-runs/{pipeline_run_id}
https://app.getorchestra.io/pipeline-runs/{pipeline_run_id}/lineage
https://app.getorchestra.io/pipeline-runs/{pipeline_run_id}/task-runs/{task_run_id}
https://app.getorchestra.io/pipelines/{pipeline_id}/runs/{pipeline_run_id}
https://app.getorchestra.io/pipelines/{pipeline_id}
```

The IDs are UUIDs (e.g. `286cb489-54f0-499b-b531-b84e3909ac9b`). If a URL contains a
pipeline_run_id, skip straight to Step 2. If it only contains a pipeline_id, query for
the latest failed run of that pipeline.

For custom/self-hosted Orchestra instances, the base domain may differ (e.g.
`https://orchestra.company.com/...`). The path structure is the same — extract UUIDs
from path segments.

### Raw UUIDs
If the user pastes a bare UUID, try it as a pipeline run ID first with
`get_pipeline_run_status`. If that returns a result, proceed to Step 2.
If not, treat it as a pipeline ID and query recent runs with `list_pipeline_runs`.

### Pipeline names or aliases
If the user says "fix the daily-etl pipeline", search for it with `list_pipelines`
and match by name or alias, then query for its latest failed run.

### Error messages
If the user pastes an error message or log snippet, skip to Step 4 (Diagnose) — you
already have the evidence. Ask for the pipeline run ID only if you need to fetch
additional context like logs or artifacts.

### Slack / alert messages
Orchestra alert messages (from Slack, Teams, email, webhooks) typically contain the
pipeline name, task name, and status. Extract these and use them to find the
corresponding pipeline run via `list_pipeline_runs`/`list_task_runs`.

## Workflow overview

Execute these steps in order. Each step feeds the next. If the parsed input provides
enough information to skip ahead, jump to the relevant step.

### Step 1 — Identify failed pipeline runs

**Goal:** Find which pipeline runs have failed recently.

**If the user provided a pipeline run ID or URL:** Skip to Step 2 using the extracted ID.

**If the user said "what's broken" or similar:** Query for recent failures:
- Call `list_pipeline_runs` with `status=FAILED`
- Default to the last 7 days if no time range specified
- Present results as a concise summary: pipeline name, when it failed, trigger type, message

**If multiple failures exist:** Ask the user which one to investigate, or offer to triage all
of them starting with the most recent.

**Key fields from the response:**
- `id` — the pipeline run ID (needed for all subsequent steps)
- `pipelineName` — human-readable name
- `pipelineId` — the pipeline definition ID
- `message` — Orchestra's summary of what happened
- `triggeredBy` — what started the run (cron, sensor, manual, webhook)
- `completedAt` — when it finished failing
- `envName` — which environment (Production, Staging, etc.)

### Step 2 — Get failed task runs

**Goal:** Identify exactly which task(s) within the pipeline failed.

- Call `list_task_runs` filtered by the failed pipeline IDs and `status=FAILED`
- Also fetch `status=WARNING` task runs — they may contain useful context

**Key fields from each task run:**
- `id` — task run ID (needed for logs/artifacts)
- `taskName` — human-readable task name
- `taskId` — the task identifier in the pipeline YAML
- `integration` — which integration (e.g. `SNOWFLAKE`, `DBT_CORE`, `HTTP`, `PYTHON`)
- `integrationJob` — the specific job type (e.g. `SNOWFLAKE_RUN_QUERY`, `DBT_CORE_RUN_COMMAND`)
- `status` — FAILED or WARNING
- `message` — Orchestra's task-level message
- `externalStatus` — the status from the underlying platform (e.g. HTTP 500, dbt error code)
- `externalMessage` — the platform's error message
- `taskParameters` — what was configured on the task
- `runParameters` — runtime parameters including connection details
- `connectionId` — which credential/connection was used
- `numberOfAttempts` — how many times Orchestra retried

**Present the findings:** Show the user which tasks failed, in what order, and their error
messages. If the pipeline has multiple tasks, note which ones succeeded (they ran before
the failure point) and which were skipped (downstream of the failure).

### Step 3 — Fetch diagnostics

**Goal:** Get the raw evidence — logs, artifacts, and operations.

For each failed task run:

1. **Logs:** Call `list_task_run_logs` to list available log files. Then fetch each log
   with `download_task_run_log`. Focus on the last ~256KB of large logs using
   `range_header` (for example `bytes=-262144`).

2. **Artifacts:** Call `list_task_run_artifacts`. For dbt tasks, look for
   `run_results.json` and `manifest.json`. Download relevant artifacts with
   `download_task_run_artifact`.

3. **Operations:** Call `list_operations` filtered by `task_run_id` to see
   sub-operations (individual dbt models, Snowflake queries, etc.) and their statuses.

**Read `../../references/orchestra/pipeline/diagnosis-patterns.md`** before proceeding to Step 4. It contains
integration-specific error patterns that will help classify the failure.

### Step 4 — Diagnose the error

**Goal:** Classify the failure and identify the root cause.

This is the analytical step. Using all evidence from Steps 1-3 plus the patterns in
`../../references/orchestra/pipeline/diagnosis-patterns.md`:

1. **Decide code vs platform.** If the failure is ingestion/sync infrastructure or another
   vendor-managed integration (Fivetran, Airbyte, Estuary, etc.), surface `platformLink` and
   `connectionId` and stop — do not open a Git PR. If the failure is in repo SQL, dbt, Python,
   or misconfigured pipeline YAML, proceed with remediation. See
   `../../references/orchestra/pipeline/diagnosis-patterns.md` (TOOL_OR_INFRASTRUCTURE).

2. **Classify the error category.** Common categories:
   - `AUTH_FAILURE` — credentials expired, rotated, or insufficient permissions
   - `TIMEOUT` — task exceeded configured timeout or underlying platform timed out
   - `QUERY_ERROR` — SQL syntax error, missing table/column, type mismatch
   - `RESOURCE_CONFLICT` — sync job already running, resource locked
   - `NETWORK_ERROR` — firewall, VPN, DNS resolution, connection refused
   - `CONFIG_ERROR` — invalid parameters, missing required fields, wrong environment
   - `DEPENDENCY_FAILURE` — upstream task failed, missing input data
   - `PLATFORM_ERROR` — the underlying platform (Snowflake, dbt Cloud, etc.) had an outage
   - `CODE_ERROR` — Python script error, dbt model compilation failure
   - `RATE_LIMIT` — API rate limit hit on the underlying platform
   - `DATA_ERROR` — data quality test failure, schema drift, unexpected nulls

3. **Identify the root cause.** Be specific. Not just "query error" but "column
   `user_email` does not exist in table `analytics.users` — likely a schema migration
   that removed or renamed the column."

4. **Check the knowledge store** for similar past fixes. Read `../../references/orchestra/pipeline/knowledge-store.md`
   if it exists (it may not exist on first run — that's fine, skip this check).

5. **Present the diagnosis** clearly to the user:
   - Error category
   - Root cause (specific)
   - Evidence (which log line, which error message, which operation failed)
   - Confidence level (high/medium/low)

**Read `../../references/orchestra/pipeline/remediation-playbooks.md`** before proceeding to Step 5.

### Step 5 — Apply the fix

**Goal:** Fix the issue or tell the user exactly what to do.

Based on the diagnosis, consult `../../references/orchestra/pipeline/remediation-playbooks.md` and take action:

**Fixes the agent can apply directly:**
- **Retry** — if the error is transient (timeout, rate limit, platform blip), trigger a
  re-run with `start_pipeline`
- **Update pipeline YAML** — if the pipeline is Orchestra-backed (not Git-backed), use
  `update_pipeline` to fix configuration errors like wrong parameters, missing
  environment variables, or incorrect task ordering
- **Re-run with different inputs** — use `run_inputs` in `start_pipeline` to override
  problematic input values
- **Open a PR** — for any code fix in a Git-backed pipeline (missing file, wrong config,
  dbt model error, etc.), use the `gh` CLI to create a pull request with the fix directly.
  Do not ask the user to make the change themselves. Workflow:
  1. Clone the repo (or use the working directory if already cloned)
  2. Check out a new branch off the failing branch (e.g. `fix/missing-pyproject-toml`)
  3. Apply the fix
  4. Commit and push
  5. Open a PR via `gh pr create` targeting the failing branch
  6. Share the PR URL with the user
  7. Immediately begin polling the PR — proceed to **Step 5b** without waiting for the user

**Fixes that require user action (explain clearly — but still poll after PR if one was opened):**
- Credential rotation — tell them exactly which connection to update and where in the UI
- Firewall/network — provide the Orchestra IPs to whitelist
- Permission grants — show the exact GRANT statement or IAM policy change

**Always explain what you're doing and why before taking action.**

### Step 6 — Retry and monitor

**Goal:** Confirm the fix worked.

This step is entered either (a) directly after a non-PR fix, or (b) automatically from Step 5b
once the PR is merged.

1. Trigger a new pipeline run via `start_pipeline`
   - Use the same pipeline ID and environment as the failed run
   - Pass any corrected `run_inputs` if applicable
   - For PR-triggered reruns, no confirmation needed — merge was the approval
2. Poll `get_pipeline_run_status` every ~30 seconds
3. Report the outcome:
   - **Succeeded:** Update the knowledge store (see Learning loop below).
   - **Failed again (same error):** The fix didn't work. Go back to Step 4 with new evidence.
   - **Failed (different error):** New problem uncovered. Restart from Step 3.

### Learning loop — Update the knowledge store

After every successful fix, record what was learned. Create or append to
`../../references/orchestra/pipeline/knowledge-store.md` with:

```
## Fix: [DATE] — [Pipeline Name]
- **Error category:** [category]
- **Integration:** [integration type]
- **Root cause:** [specific description]
- **Fix applied:** [what was done]
- **Time to fix:** [how long the process took]
- **Confidence:** [was the first diagnosis correct?]
```

Also update `../../references/orchestra/pipeline/diagnosis-patterns.md` if a new pattern was discovered that
isn't already documented.

On first run for a new user, also query `list_task_runs` with `status=FAILED` across all recent
runs to build a profile of which integrations fail most often. Store this in the knowledge
store as a "failure frequency" section.

## Output formatting

**Be succinct.** Users are engineers dealing with broken pipelines — they want facts and
actions, not explanations. No preamble, no summaries of what you just did, no "great news".
If the answer fits in one line, use one line. Cut any sentence that doesn't add new information.

All user-facing output must follow these templates exactly. Consistent structure makes it easy
to scan at a glance — especially when there are multiple failures to triage.

---

### Triage view (Step 1 — multiple pipelines)

Use a table. One row per distinct pipeline (deduplicate by `pipelineId`). Newest failure first.
After the table, add a one-line callout for any that are feature branch runs (skip them).

```
## Failing Pipelines — Workspace Triage

| Pipeline | Category | Failing Task | Root Cause |
|---|---|---|---|
| `name` | `CATEGORY` | Task name | One-line plain-English description |

> **Skipped (feature branch):** `pipeline-name` — failures are on branch `x`, main is healthy.
```

Always end the triage with a prompt offering to dig into specific pipelines:
```
Which would you like me to investigate? I'd suggest starting with X because Y.
```

---

### Single pipeline diagnosis (Step 4)

Use a consistent header and structured block every time, then evidence and confidence.

```
## Diagnosis: `<pipeline name>`

**Error category:** CATEGORY
**Root cause:** One specific sentence — not "query error" but exactly which object/column/table.
**Integration:** DBT_CORE / DBT_CORE_EXECUTE (or similar)
**Connection:** connection-id-here
**Confidence:** High / Medium / Low

**Evidence:**
- Exact log line or error message (quoted)
- Which operation or model failed
- Any corroborating signals (exit code, attempt count, etc.)
```

---

### Fix options (Step 5)

Always present options as a numbered list with a clear owner label on each:

```
**Fix options:**

1. **[Agent can apply]** Short description of what will be done and why it fixes the issue.
2. **[Agent opens a PR]** For code changes in Git-backed pipelines — describe what file/change
   will be committed and which branch the PR targets.
3. **[User action needed]** Only for things the agent genuinely cannot do: credential rotation,
   firewall changes, permission grants. Include the specific UI path, command, or SQL.
4. **[Needs more info]** What you'd need to know to proceed (e.g. "Does the EVENTS table
   exist? Run: SELECT COUNT(*) FROM SNOWFLAKE_WORKING.PUBLIC.EVENTS").

Recommended: Option N — one sentence on why this is the right call.
```

Never present options without a recommendation. Never use vague labels like "you could try".
Never label a code fix as `[User action needed]` — open the PR instead.

---

### Retry status (Step 6)

During polling, emit a single line per status check. Do not repeat the full context.

```
▶ Run e2049b86 — RUNNING (0:42 elapsed)
▶ Run e2049b86 — RUNNING (1:30 elapsed)
✅ Run e2049b86 — SUCCEEDED (2:15 elapsed)
```

On failure during retry, immediately switch to diagnosis format (don't just say "it failed").

---

### Resolution summary (after successful fix)

Always end a successful fix with a compact summary block:

```
## Fixed: `<pipeline name>`

- **Run:** `<new-run-id>` — SUCCEEDED
- **Root cause:** (one line)
- **Fix applied:** (one line)
- **Duration:** X min
- **Knowledge store:** Updated ✓
```

---

## Important notes

- **Never expose secrets.** Log contents may contain credentials, tokens, or connection strings.
  Summarise errors without reproducing sensitive values.
- **Confirm before destructive actions.** Always ask the user before retrying a pipeline that
  writes data (ingestion, materialisation, reverse ETL). Idempotent pipelines (tests, queries)
  can be retried with just a heads-up.
- **Respect environments.** If the failure was in Production, be extra cautious. Suggest testing
  the fix in a Development/Staging environment first if one exists.
- **Rate limit awareness.** The Orchestra metadata backend returns 7 days of data by default and has
  pagination. Don't make excessive MCP calls — batch where possible.
- **Git-backed vs Orchestra-backed.** Only Orchestra-backed pipelines can be updated via
  `update_pipeline`.
  Git-backed pipelines require code changes committed to the repository. Check `storageProvider`
  in the `list_pipelines` response to determine which type it is.
