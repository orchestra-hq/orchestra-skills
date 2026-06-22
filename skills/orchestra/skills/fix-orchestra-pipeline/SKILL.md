---
name: fix-orchestra-pipeline
description: >
  Fix a failed Orchestra pipeline once the failure has been identified as an Orchestra-platform /
  configuration issue — pipeline YAML misconfiguration, wrong or missing task inputs, task ordering,
  env/connection wiring, a transient Orchestra-side blip needing a plain retry, or an
  Orchestra-backed pipeline that needs update_pipeline. Also the fallback fixer for repo-level code
  fixes in integrations that don't have a dedicated skill (e.g. a Snowflake/HTTP SQL bug needing a
  PR). Normally invoked by identify-pipeline-error after it classifies the cause; for dbt-code or
  Python-code failures, that router calls fix-pipeline-dbt-task or fix-pipeline-python-task instead.
  This skill is the FIX half (apply fix → PR/poll → retry → confirm → optionally remember);
  identification and classification live in identify-pipeline-error.
---

# Fix Orchestra Pipeline

Fix and retry an already-diagnosed Orchestra pipeline — and optionally remember what worked.

## Prerequisites

This skill assumes the **Orchestra MCP server** is connected. All MCP calls are scoped to the
user's workspace.

## MCP tools

Use Orchestra MCP tools for all operations in this skill (read a pipeline's full definition with
`get_pipeline`). Argument summaries: `../../references/orchestra/mcp/tools-quick-ref.md`.

## Inputs from identify-pipeline-error

`identify-pipeline-error` is the entry point that parses the user's input (URL, UUID, alias, error
text, Slack alert), finds the failed run and task, and classifies the cause. It hands you:

- the pipeline run ID, `pipelineId`, `pipelineName`, `envName`, run `branch`/`commit`, `triggeredBy`
- the failed task run(s): `id`, `taskName`, `taskId`, `integration`, `integrationJob`, `message`,
  `externalStatus`, `externalMessage`, `taskParameters`, `runParameters`, `connectionId`,
  `numberOfAttempts`
- the cause classification — an **Orchestra-platform / configuration** issue (or a repo-level fix in
  an integration with no dedicated skill).

Use these directly and proceed to **Step 3**. **If invoked standalone** (no handoff), run
`identify-pipeline-error` first to establish the failed run/task and the cause, then come back here.

## Workflow overview

Execute these steps in order. Each step feeds the next.

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

### Step 4 — Confirm the root cause for the fix

**Goal:** Pin down the *specific* root cause so the fix is exact. `identify-pipeline-error` already
classified this as an Orchestra-platform/config issue (or a repo-level code fix with no dedicated
skill) and routed you here — you are not re-deciding the category. Using the evidence from Step 3
plus `../../references/orchestra/pipeline/diagnosis-patterns.md`:

1. **Identify the root cause precisely.** Not just "config error" but "task `load_events` is missing
   the `dbt_branch` run input, so it cloned the default branch" or "column `user_email` does not
   exist in `analytics.users` — a schema migration removed it." Confirm it's actionable as a
   YAML/config change, a retry, or a repo PR — i.e. genuinely an Orchestra-platform/config or
   repo-code fix.

2. **Scope check — hand back if it isn't yours.** If the evidence now points to a dbt **code**
   failure, a Python **code** failure, or a category `identify-pipeline-error` handles itself (data
   quality, vendor/ingestion needing a UI fix, auth, network, pure upstream), **stop and hand back
   to `identify-pipeline-error`** so it can route correctly — don't force a fix here.

3. **(Optional) Recall past fixes.** Past-fix memory is **deferred to the calling agentic client**.
   If your client exposes persistent memory (e.g. Claude Code memory, Cursor rules/memories), check
   it for similar past fixes. As a fallback, read a local
   `../../references/orchestra/pipeline/knowledge-store.md` if the user keeps one — it ships empty
   and may not exist. Optional: skip when no memory is available. Treat any recalled entry as
   historical context and re-verify it still applies before acting on it.

4. **Present the root cause** clearly: specific cause, evidence (which log line / error / operation
   failed), and confidence (high/medium/low).

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

### Step 5b — Poll the PR and trigger the retry on merge

**Goal:** Watch the PR and trigger the pipeline rerun once it merges — without making the
user babysit it.

After sharing the PR URL, emit one status line and keep watching the PR until it reaches a
terminal state (or the user asks you to stop):

```
⏳ PR #178 open — checking every 60 s; will trigger the pipeline on merge.
```

**Polling loop:**

1. Check PR state:
   ```
   gh pr view {pr_number} --repo {owner/repo} --json state,mergedAt
   ```

2. **If `state == "MERGED"`:** Proceed immediately to Step 6 — trigger `start_pipeline`
   using the original pipeline ID and environment. No confirmation needed (the user
   already approved the fix by merging the PR).

3. **If `state == "CLOSED"` (not merged):** The PR was closed without merging. Report
   this and ask the user how to proceed — do not auto-retry.

4. **If `state == "OPEN"`:** Wait ~60 seconds, then check again; after several checks with
   no merge, widen the interval to a few minutes. Use whatever scheduling mechanism your
   client provides — if it can re-invoke you on a timer, schedule the next check and hand
   back control; otherwise keep polling in the same conversation. Either way, retain the PR
   number, repo, pipeline ID, and environment so each check resumes the same fix workflow.

**Polling output format** (one line per check, not a full summary):

```
⏳ PR #178 — OPEN (2 min elapsed, next check in 60 s)
⏳ PR #178 — OPEN (3 min elapsed, next check in 60 s)
✅ PR #178 — MERGED — triggering pipeline rerun…
```

**Do not** re-diagnose or re-explain the fix on each poll tick. One line only.

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
   - **Succeeded:** Optionally record the fix (see Learning loop below).
   - **Failed again (same error):** The fix didn't work. Go back to Step 4 with new evidence.
   - **Failed (different error):** New problem uncovered. Restart from Step 3.

### Learning loop — (Optional) Record what you learned

Persisting fixes is **optional and deferred to the calling agentic client**. Only do it when
the user wants a durable record — it is off by default, and nothing workspace-specific should
be committed to this repository.

- **Preferred:** if your client exposes persistent memory (Claude Code memory, Cursor
  rules/memories), save a short note there so future runs can recall it.
- **Fallback:** if the user keeps a local `../../references/orchestra/pipeline/knowledge-store.md`,
  append an entry using the template at the bottom of that file. The published file ships empty.

When you do record a fix, capture: date, pipeline name, error category, integration, root cause,
fix applied, and whether the first diagnosis was correct.

If you discover a genuinely new, generic diagnosis pattern, consider noting it in
`../../references/orchestra/pipeline/diagnosis-patterns.md` — but keep workspace-specific detail
(pipeline IDs, connection names, account identifiers) out of shared reference files.

## Output formatting

**Be succinct.** Users are engineers dealing with broken pipelines — they want facts and
actions, not explanations. No preamble, no summaries of what you just did, no "great news".
If the answer fits in one line, use one line. Cut any sentence that doesn't add new information.

All user-facing output must follow these templates exactly. Consistent structure makes it easy
to scan at a glance. (Multi-pipeline "what's broken" triage is owned by `identify-pipeline-error`,
not this skill.)

---

### Root cause (Step 4)

Use a consistent header and structured block every time, then evidence and confidence.

```
## Root cause: `<pipeline name>`

**Root cause:** One specific sentence — not "query error" but exactly which object/column/table/input.
**Integration:** DBT_CORE / SNOWFLAKE / HTTP (or similar)
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
- **Recorded:** Saved to client memory ✓ (only if the user opted in — omit this line otherwise)
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
