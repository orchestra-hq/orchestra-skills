---
name: triage-orchestra-pipeline
description: >
  Diagnose a failed Orchestra pipeline, open a fix PR, validate it on a branch run, then
  present a human-readable triage summary and STOP for user approval before merging.
  Use this when the user wants to review the fix before it goes to main — not for fully
  automated fixes. Trigger on phrases like "triage my pipeline", "show me what's broken",
  "investigate but don't fix yet", "prepare a fix for review", or when the user explicitly
  wants a review gate before applying changes. Also trigger when the user describes a
  symptom in a downstream system ("dashboard looks wrong", "chart is stale", "dbt model
  has bad data") even if no pipeline error exists — the skill will trace the symptom upstream.
---

# Triage Orchestra Pipeline

Diagnose a failed (or symptom-reported) pipeline, open a fix PR, validate it on the
branch, then present a compact triage report and stop for human approval. Nothing merges
to main until the user says so.

## Shared references

Orchestra docs live under `references/orchestra/`. Index and layout: `../../references/orchestra/README.md`. Paths below are relative to this skill folder.

**Pipeline**

- `../../references/orchestra/pipeline/diagnosis-patterns.md` — error classification
- `../../references/orchestra/pipeline/remediation-playbooks.md` — fix strategies
- `../../references/orchestra/pipeline/knowledge-store.md` — (optional) local fix history; prefer your client's persistent memory

**MCP**

- `../../references/orchestra/mcp/tools-quick-ref.md` — tool arguments and behaviour (use `get_pipeline` to read a pipeline's full definition)

## Workflow

### Step 0 — Parse the prompt: error-first or symptom-first?

Before doing anything, classify the input:

**Error-first** — the pipeline has a red status, or the user gives a run ID/URL/UUID, or
says "my pipeline failed". Skip to **Step 1**.

**Symptom-first** — the user describes something wrong in a downstream system without
mentioning a pipeline error: "Lightdash dashboard looks wrong", "numbers are off",
"chart is stale", "dbt model returning bad values". Go to **Step 0b**.

---

### Step 0b — Symptom-first: start at the named layer, traverse upstream

**Goal:** Find the root cause by starting at the system the user named and walking
backwards through the pipeline until something is wrong.

#### 0b-1. Map the symptom to a pipeline task

Extract the system keyword from the prompt (e.g. "Lightdash", "dbt", "Fivetran").
Call `list_pipeline_runs` for the relevant pipeline to get the most recent run.
Call `list_task_runs` for that run to get all tasks and their execution order.

Match the keyword to a task via the `integration` field (e.g. `LIGHTDASH`, `DBT_CORE`,
`FIVETRAN`). This is the **entry task**. If no pipeline is named, ask the user which
pipeline to check before proceeding.

#### 0b-2. Inspect the entry task

For the entry task in the most recent run, check three things in order:

1. **Run status.** Was it SUCCEEDED, WARNING, SKIPPED, or FAILED? Note it — even a
   SUCCEEDED task can produce wrong output if its inputs were bad.

2. **Recent code commits.** Identify the git repo for this task from `runParameters`
   (`branch`, `commit`, `platformLink`). Fetch the last 10 commits on that branch:
   ```
   gh api repos/<owner>/<repo>/commits?sha=<branch>&per_page=10
   ```
   For each commit in the last 7 days, check the diff for changes to files relevant
   to the symptom. Examples:
   - Lightdash symptom → check `.yml` metric/dimension definitions, `schema.yml` joins
   - dbt symptom → check model SQL, schema tests, macros, seeds
   - Fivetran symptom → check connector config, transformation logic
   Flag any commit whose diff touches the area the user described as wrong.

3. **Artifacts/logs.** Download available artifacts (e.g. dbt `run_results.json`) and
   check for warnings or row count anomalies even on technically passing runs.

**Decision:**
- Suspicious commit or anomaly found → this is the root cause. Proceed to **Step 2**.
- Nothing found → move to the next upstream task (Step 0b-3).

#### 0b-3. Traverse upstream one layer at a time

Walk backwards through the pipeline task list by execution order. For each upstream task,
repeat Step 0b-2: check run status, recent commits in its repo, and artifacts.

**Example traversal order** for a Fivetran → dbt → Lightdash pipeline:
```
Prompt: "Lightdash dashboard looks wrong"

Layer 1: Lightdash task
  → status: SUCCEEDED
  → commits: no changes in last 7 days
  → no issue found → move upstream

Layer 2: dbt task
  → status: SUCCEEDED
  → commits: found commit 3 days ago changing model SQL in affected area
  → STOP — root cause identified

(Layer 3: Fivetran task — not reached)
```

Stop as soon as a suspicious commit or anomaly is found. Do not keep looking once a
cause is identified.

If traversal reaches the source with nothing found across all layers, report:
"No issues found in the last 7 days across all layers" with a table of what was checked
at each layer (task, status, commits reviewed, conclusion).

#### 0b-4. Treat the suspect commit as the root cause

Once identified, classify it exactly as you would an error-first diagnosis:
- **Error category:** CODE_ERROR (logic change), DATA_ERROR (bad values), CONFIG_ERROR, etc.
- **Root cause:** the specific commit, file, and line that caused the symptom

Proceed to **Step 2**.

If the commit represents an intentional business logic change (not a bug), do not open a
revert PR. Instead, present the triage summary with a **[User action needed]** resolution:
explain which commit introduced the change and ask the user to decide whether to revert or
adjust the downstream layer to match the new logic.

---

### Step 1 — Identify & diagnose (error-first path)

Run the full diagnosis: find the failed run, get task runs, fetch logs/artifacts/operations,
classify the error, identify root cause. Read `../../references/orchestra/pipeline/diagnosis-patterns.md`;
optionally recall similar past fixes from your client's persistent memory (or a local
`../../references/orchestra/pipeline/knowledge-store.md` if the user keeps one).

Do not present a verbose diagnosis block to the user yet. Collect all findings silently —
the output comes at the end in the triage summary.

---

### Step 2 — Open fix PR (do NOT merge)

Apply the fix exactly as in `fix-orchestra-pipeline` Step 5:
- For code fixes: branch off the failing branch, apply changes, push, open PR via `gh pr create`
- For config fixes: use `update_pipeline` if Orchestra-backed

**Critical difference:** Do NOT merge. Do NOT call `gh pr merge`. Leave the PR open.

Collect:
- PR number and URL
- Branch name
- Exact files and lines changed
- One-sentence reason the change fixes the failure

---

### Step 3 — Validate on the fix branch

Trigger a pipeline run against the fix branch (not main) to prove the fix works before
anyone merges it:

```python
start_pipeline(
    alias_or_pipeline_id=<pipeline_id>,
    branch=<fix-branch-name>,
    environment=<same env as the failed run>
)
```

Poll `get_pipeline_run_status` every 60 s until terminal (SUCCEEDED / FAILED / WARNING).

- **SUCCEEDED:** Fix is validated. Proceed to Step 4.
- **FAILED (same error):** Fix didn't work. Return to Step 2, update the PR, re-validate.
- **FAILED (different error):** New problem uncovered. Diagnose it, extend the PR, re-validate.
- **WARNING:** Treat as passing unless the warning is in the same model/test that was
  originally failing. Note it in the triage summary.

Do not present anything to the user until the branch run reaches a terminal state.

If the pipeline writes data (ingestion, reverse-ETL), warn the user before running:
"This pipeline writes data — branch run will also write. Proceed?"

---

### Step 4 — Present triage summary and STOP

Output the triage summary in the format below, then explicitly stop.
Do not schedule a wakeup. Do not merge anything. Wait for the user.

---

## Triage output format

Optimised for Slack: scannable, no preamble, decision-ready.

### Error-first format

```
## Triage: `<pipeline name>`

**What broke:** <one sentence — which task, which test/error>
**Why:** <one sentence — specific root cause>

| Value / change | Field | Origin |
|---|---|---|
| `VALUE` | `column_name` | API enum expansion / bad commit / etc. |

---
**How it was found:**
1. `list_task_runs` → dbt task FAILED, exit code 1
2. Downloaded `run_results.json` → 3 `accepted_values` test failures
3. `list_operations` → `REUSED` present in live operation data

---
**PRs opened:**

| PR | File | Change |
|---|---|---|
| [#N](url) | `models/staging/schema.yml` | Added `REUSED` to `operation_status` accepted values |

**Branch validation:** Run `<run-id>` on `<branch>` — ✅ SUCCEEDED / ❌ FAILED

---
**Why this fixes it:** <2–3 sentences on what the test does, why the new value broke it,
and why this is the right fix rather than a data issue.>

---
> **Ready to apply?** Reply `merge` to merge the PR(s) and trigger a production run,
> or `reject` to close them.
```

### Symptom-first format

```
## Triage: `<pipeline name>` — symptom: "<user's description>"

**Entry layer:** <system the user named>
**Root cause found at:** <layer where the issue was identified>
**What changed:** Commit `<sha>` on `<date>` — "<commit message>"

---
**Layers checked:**

| Layer | Task status | Commits checked | Finding |
|---|---|---|---|
| Lightdash | SUCCEEDED | 0 in last 7d | Clean |
| dbt Core | SUCCEEDED | 4 in last 7d | ⚠️ Commit `abc1234` changed `store_sales_example.sql` |
| Fivetran | — | not reached | — |

---
**Suspect commit diff:**
- File: `models/clean/store_sales_example.sql`
- Change: `WHERE sales > 0` → `WHERE sales > 1000` (filters out low-value stores)

---
**PRs opened:**

| PR | File | Change |
|---|---|---|
| [#N](url) | `models/clean/store_sales_example.sql` | Reverted threshold change |

**Branch validation:** Run `<run-id>` on `<branch>` — ✅ SUCCEEDED / ❌ FAILED

---
**Why this fixes it:** <explanation of the causal chain from the commit to the symptom>

---
> **Ready to apply?** Reply `merge` to merge and trigger a production run,
> or `reject` to close the PR(s).
> If this was an intentional change, reply `intentional` and I'll investigate the
> downstream layer instead.
```

---

## Approval handling

**`merge`** (or: "yes", "approve", "ship it", "lgtm"):
1. `gh pr merge <N> --repo <owner/repo> --squash --delete-branch` for each PR
2. `start_pipeline(pipeline_id, environment=Production)`
3. Poll until terminal, output resolution summary
4. (Optional) Record the fix in your client's persistent memory — or a local `../../references/orchestra/pipeline/knowledge-store.md` if the user keeps one. Off by default.

**`reject`** (or: "no", "close it", "abandon"):
1. `gh pr close <N> --repo <owner/repo>` for each PR
2. Report closed. Stop.

**`intentional`** (symptom-first only — the commit was deliberate, not a bug):
1. Do not revert. Close the open PR.
2. Re-enter the traversal at the next downstream layer — the fix may need to be
   in Lightdash config to match the new dbt logic, rather than reverting dbt.
3. Re-present the triage summary for the downstream fix.

**User provides feedback** ("change X to Y", "also fix Z"):
1. Apply changes to the existing PR branch, push (do not open a new PR)
2. Re-run branch validation (Step 3)
3. Re-present triage summary with updated diff and new run result

---

## Important notes

- **Never auto-merge.** The entire purpose of this skill is the human review gate.
- **One PR per logical fix.** If multiple files need the same change, one PR covers all.
- **Symptom traversal stops at first finding.** Do not keep looking once a cause is
  identified — present it and let the user decide if it's the right one.
- **Commits are suspects, not convictions.** If a commit looks related but you're not
  certain, say so in the triage summary and give the user the option to investigate
  further before opening a PR.
- **Recall/record is optional.** Past-fix memory is deferred to the calling agentic client
  (Claude Code memory, Cursor rules), with a local `knowledge-store.md` as an opt-in fallback —
  see `fix-orchestra-pipeline`. Never commit workspace-specific fix history to this repo.
