# Orchestra best-practices checklist (review rubric)

The rubric for `review-orchestra-account`. Each check states what good looks like, the MCP signal
that detects a violation, a default severity, and the doc path to cite (prefix with the docs host,
e.g. `https://docs.getorchestra.io`). Severities are defaults — adjust to real impact and the
user's maturity. `[MANUAL]` marks checks the MCP can't see; surface those under **Manual
verification** instead of asserting pass/fail.

Detection runs against data from Step 2: `list_pipelines` (inventory + `storageProvider` + schedule),
`get_pipeline` (full definition), `list_pipeline_runs`/`list_task_runs`/`list_operations` (runtime),
`list_assets` (governance). Match field names on concept, not one spelling (`max_active`/`maxActive`,
`set_outputs`/`setOutputs`, `task_groups`/`taskGroups`).

## Contents

1. Pipeline design and structure
2. Environments and promotion
3. Version control, Git and CI/CD
4. Connections and credentials
5. Alerting and observability
6. Security and access control
7. Performance and cost
8. Account-review quick checklist

---

## 1. Pipeline design and structure

**1.1 One pipeline per process, not per environment** — *Medium*
Good: a single pipeline reused across environments. Signal: in `list_pipelines`, near-duplicate
names/aliases differing only by an environment suffix (`_staging`/`_prod`/`_dev`, `-uat`), or many
pipelines with near-identical task structure in `get_pipeline`. → Consolidate to one pipeline with
environment overlays. Docs: `/docs/core-concepts/pipelines`, `/docs/core-concepts/environments`.

**1.2 Use Task Groups for dependency wiring** — *Low*
Good: downstream tasks `depends_on` a task group, not every individual ingestion task. Signal: in
`get_pipeline`, a task with a long `depends_on` list naming many sibling tasks instead of one group.
→ Group related work; depend on the group. Docs: `/docs/core-concepts/tasks/task-groups`.

**1.3 MetaEngine instead of duplicated tasks/pipelines** — *Medium*
Good: a `matrix` block where the same work runs over many inputs (tables, files, customers, dates).
Signal: repeated tasks in one pipeline that differ only by a parameter value, or sibling pipelines
that differ only by such a value, with no `matrix`. → Convert to a MetaEngine matrix; give each
matrix input an object with a unique `id` key for stable child IDs. Docs:
`/docs/core-concepts/tasks/metaengine`.

**1.4 Control matrix parallelism deliberately** — *Low*
Good: matrix pipelines set `max_parallel` (or run sequentially for rate-limited APIs) and choose
Task Group `Parallel`/`Sequential` on purpose. Signal: a `matrix` with no `max_parallel` feeding a
known rate-limited integration. → Set concurrency at both levels. Docs:
`/docs/core-concepts/tasks/metaengine`.

**1.5 Branch on task status, not custom callables** — *Low*
Good: branching uses `condition` referencing `tasks['id'].status`, `task_groups['id'].all().status`,
inputs, or `format_date(...)`. Signal: branching via bespoke Python callables where a status
condition would do; or conditions that ignore a possible `SKIPPED` upstream (use
`... in ['SUCCEEDED','SKIPPED']`). → Use the branching UI / `condition`. Docs:
`/docs/core-concepts/pipelines/branching`, `/docs/core-concepts/pipelines/conditional-expressions`.

**1.6 Keep nesting shallow** — *Low*
Good: MetaEngine over chained child pipelines; at most one layer of triggered pipelines; pipeline
triggers for linear `A → B → C`. Signal: chains of triggered pipelines more than one level deep.
→ Flatten with the MetaEngine / single-layer triggers. Docs: `/docs/core-concepts/triggers/pipeline`.

**1.7 Orchestrate in Orchestra, run compute where it belongs** — *Low*
Good: heavy compute runs in Snowflake/Databricks/containers; failures fixed at source then
**Rerun from Failed**. Signal: inline Python doing heavy data crunching that belongs in the
warehouse. → Push compute down. Docs:
`/docs/core-concepts/pipelines/running-and-retrying-pipelines`.

**1.8 Set pipeline concurrency where overlap is undesirable** — *High*
Good: `configuration.concurrency.max_active` (a.k.a. `maxActive`) is set on pipelines where
overlapping runs would corrupt data or double-spend compute. Signal: a frequently scheduled or
sensor-triggered pipeline with no concurrency limit; or `list_pipeline_runs` showing overlapping
RUNNING windows. Note: at the limit Orchestra **skips** the new run (no queue, no cancel), evaluated
per pipeline + environment (+ Git branch). → Set `max_active`. Docs:
`/docs/core-concepts/pipelines/pipeline-runs#how-pipeline-concurrency-works`.

**1.9 Prefer inputs/env vars/conditionals over duplication** — *Medium*
Good: variation handled with `${{ inputs.* }}`, `${{ ENV.* }}`, and conditional expressions. Signal:
duplicated pipelines/tasks that differ only by a hardcoded dimension. → Parameterise. Docs:
`/docs/core-concepts/variables/inputs`, `/docs/core-concepts/variables/environment-variables`.

**1.10 Unique task and task-group IDs** — *High*
Good: every task ID and task-group ID is unique. Signal: duplicate IDs in `get_pipeline` (these can
produce a pipeline that runs but 404s in the editor). → Rename to unique IDs. Docs:
`/docs/core-concepts/pipelines/schema`, `/docs/faq`.

## 2. Environments and promotion

**2.1 Don't run one pipeline per environment** — *Medium*
Good: task params and connections reference `${{ ENV.VARIABLE_NAME }}` with the **same** variable
names across every environment. Signal: same as 1.1, plus hardcoded environment-specific values
(warehouse names, schemas) inline in task params instead of `${{ ENV.* }}`. → Use environment
overlays. Docs: `/docs/core-concepts/environments`.

**2.2 Run at least dev + prod (+ staging for CI/CD)** — *Low* `[MANUAL]`
Good: differences live in data-store connections, not orchestration logic. Environment list isn't
fully exposed by MCP — flag for manual check, but note inline hardcoded environment differences if
you see them. Docs: `/docs/core-concepts/tasks/connections`.

**2.3 Use inputs for run-time parameters** — *Low*
Good: backfill dates etc. come from `${{ inputs.* }}`, fixed at run start and passed downstream via
task outputs (not mutated mid-run). Signal: hardcoded dates/params that clearly should be inputs.
→ Add pipeline inputs; combine with the matrix to fan out backfills. Docs:
`/docs/core-concepts/variables/inputs`.

**2.4 Don't assume duplicate tool instances per environment** — *Low* `[MANUAL]`
Good: avoid dual Fivetran/etc. accounts that double cost; keep at least a test data area. Not
visible to MCP — flag for manual check.

## 3. Version control, Git and CI/CD

**3.1 Production pipelines are Git-backed** — *High*
Good: production pipelines have a Git `storageProvider` (`GITHUB`/`GITLAB`/`BITBUCKET`/`ADO`).
Signal: `list_pipelines` shows `storageProvider: ORCHESTRA` (UI-only) on production-bound pipelines.
→ Download YAML, commit it, work on a branch, register via CLI/API. Docs:
`/docs/git-control-and-ci-cd/git-control`.

**3.2 Stable alias for register/update** — *Medium*
Good: pipelines updated via `PUT /pipelines/{alias}` / `update-pipeline` with a stable alias.
Signal: duplicate pipelines that look like repeated `import`/`POST` of the same definition (same
name, multiple entries). → Use one alias. Docs: `/docs/git-control-and-ci-cd/orchestra-cli`.

**3.3 Validate before deploy** — *Medium* `[MANUAL]`
Good: CI runs `orchestra-cli validate` / `POST /pipelines/schema` and the JSON Schema is wired into
the IDE. CI config isn't visible to MCP — flag for manual check; recommend if pipelines are Git-backed
but you can't confirm validation. Docs: `/docs/git-control-and-ci-cd/ci-cd/validation`.

**3.4 Standard promotion flow** — *Medium* `[MANUAL]`
Good: validate YAML → run `staging` on PR branches → run `production` on merge to default branch.
Scheduled/cron production runs use the default-branch file. Flag for manual check (CI lives in the
repo). Docs: `/docs/git-control-and-ci-cd/ci-cd/`, `/docs/git-control-and-ci-cd/ci-cd/github_actions`.

**3.5 dbt Slim CI: one parametrised production pipeline** — *Medium*
Good: one production pipeline with parametrised `dbt_command` / `dbt_branch` inputs, not a separate
CI-only pipeline. Signal: a distinct "CI" dbt pipeline alongside the production dbt pipeline. →
Parametrise the production pipeline; rely on `latest_production` artifacts. (Slim CI does **not**
require `use_state_orchestration`.) Docs: `/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd`.

## 4. Connections and credentials

**4.1 One connection per integration per environment, reused** — *Low*
Good: tasks reference shared connections; multiple credentials per integration only for least
privilege / dev-test isolation. Signal: many ad-hoc connections for the same integration+environment.
→ Consolidate. Docs: `/docs/core-concepts/tasks/connections`.

**4.2 Dedicated service accounts for production** — *Medium* `[MANUAL]`
Good: scheduled runs use locked-down service accounts, never a root/personal user. Connection
identities aren't fully exposed — flag for manual check. Docs:
`/docs/guides/configuration/aws-authentication`.

**4.3 Secrets in a secrets manager, never in task parameters** — *High*
Good: secrets come from integration credentials or a key vault (AWS Secrets Manager / Azure Key
Vault). Signal: in `get_pipeline`, literal-looking secrets in task params — values matching API-key/
token/password/connection-string patterns (e.g. long high-entropy strings, `sk-`, `AKIA`, `xoxb-`,
`postgres://user:pass@`) instead of `${{ ENV.* }}` or a connection ref. → Move to a secrets
manager/credential. High severity — call out the exact task and key **name** only; never record or
report the secret value itself (not even a fragment). Docs: `/docs/integrations/aws_secrets_manager`.

**4.4 Avoid plain-text env vars for sensitive values** — *High*
Good: sensitive values use integration credentials or a key vault; env vars are for non-sensitive
config only (they display in clear text). Signal: env-var names suggesting secrets (`*_KEY`,
`*_SECRET`, `*_TOKEN`, `*_PASSWORD`, `*_PAT`) used as plain-text environment variables, especially in
inline Python tasks. → Use a key vault / credential. Flag by env-var **name** only — never copy the
value into notes or the report. Docs: `/docs/guides/configuration/running-python`.

**4.5 Let Orchestra own the schedule** — *Medium* `[MANUAL]` (partial)
Good: source tools (Airbyte, Stitch, Hightouch, Fivetran) set to manual/paused and triggered from
Orchestra, one task per integration job. Signal (partial): source-tool tasks exist in pipelines (good)
— but whether the source itself is paused is set at the source tool, so flag for manual confirmation.
Docs: `/docs/core-concepts/tasks/connections`.

**4.6 Whitelist Orchestra IPs / use private connections** — *Low* `[MANUAL]`
Network config isn't visible to MCP — flag for manual check. Docs: `/docs/deployment-options`.

## 5. Alerting and observability

**5.1 Granular alerts at the right level** — *High* (if production has none)
Good: pipelines/tasks/sensors have alerts on specific statuses (`FAILED`, `WARNING`, `SUCCEEDED`,
`SKIPPED`, `CANCELLED`; sensors support `FAILED` only). Signal: in `get_pipeline`, production
pipelines with no `alerts` block, or alerts on every status (fatigue). → Add targeted alerts. High if
production has no failure alerting; Medium for fatigue/over-alerting. Docs:
`/docs/core-concepts/alerting`.

**5.2 Alerts defined in YAML (`AlertModel`)** — *Medium*
Good: alerts live in the pipeline YAML so they're version-controlled. Signal: a Git-backed pipeline
whose definition has no `alerts` block yet the user relies on alerting (likely configured in UI). →
Move alerts into YAML. Docs: `/docs/core-concepts/alerting`.

**5.3 Route by domain and severity** — *Low*
Good: per domain, a "heartbeat" channel for completions and a "failures" channel for incidents;
routed per environment via `${{ ENV.<var> }}`. Signal: all alerts to one channel, or hardcoded
channels instead of `${{ ENV.* }}`. → Split routing. Docs: `/docs/core-concepts/alerting`.

**5.4 Secure webhook alert endpoints** — *Medium*
Good: webhook destinations use Basic/Bearer/Custom Header auth. Signal: webhook alert destination
with `No Authentication`. → Add auth. Docs: `/docs/core-concepts/alerting`.

**5.5 Enable `set_outputs` only when needed** — *Low*
Good: `set_outputs` off unless an output is consumed downstream (off by default to avoid storing
sensitive data; 5 MB/run limit). Signal: `set_outputs: true` on tasks whose outputs nothing
references. → Disable where unused. Docs: `/docs/core-concepts/tasks/setting-outputs`.

**5.6 Stale assets are a governance signal** — *Low*
Good: assets have Orchestra operations within ~7 days; uncovered assets get scheduled Asset Runs.
Signal: `list_assets` entries with no operation in 7+ days (confirm via `list_operations`). → Bring
under a pipeline / schedule Asset Runs. Docs: `/docs/core-concepts/assets`.

## 6. Security and access control

All `[MANUAL]` — RBAC, workspace, API-key, IP, and deployment settings aren't exposed by the MCP.
List these under **Manual verification**; recommend based on what the user reports.

**6.1 Roles assigned deliberately** `[MANUAL]` — Admins/Editors/Maintainers/Operators/Viewers and
custom groups scoped to least privilege. Docs: `/docs/organisation-settings/Role-based-access-control`.
**6.2 Workspaces isolated; tokens clearly named** `[MANUAL]` — no cross-workspace resources; token
names like `ORCHESTRA_WORKSPACENAME_TOKEN`. Docs: `/docs/organisation-settings/workspaces`.
**6.3 API keys in a secrets manager and rotated** `[MANUAL]` — rotate via Workspace Settings. Docs:
`/docs/organisation-settings/api-key`.
**6.4 IP restrictions (CIDR), include current network** `[MANUAL]` — Docs:
`/docs/organisation-settings/ip-restrictions`.
**6.5 Deployment model fits requirements** `[MANUAL]` — SaaS / hybrid / private connections. Docs:
`/docs/deployment-options`.

## 7. Performance and cost

**7.1 Trigger on readiness with sensors, not over-scheduled cron** — *Medium*
Good: sensors with sensible `timeout_mins` and status checks; **Check latest** on the Orchestra
pipeline sensor for mismatched cadences. Signal: high-frequency cron schedules where a sensor fits,
or `list_pipeline_runs` showing many runs that do no work. → Switch to sensors. Docs:
`/docs/core-concepts/triggers/sensors`.

**7.2 `LIMIT` on SQL sensor checks; file prefix for object-store sensors** — *Low*
Good: SQL sensor checks add `LIMIT` when result data isn't needed downstream; S3/ADLS sensors use a
file prefix on large buckets. Signal: SQL sensor check query with no `LIMIT`; object-store sensor
with no prefix. → Add them. Docs: `/docs/core-concepts/triggers/sensors`.

**7.3 Skip unnecessary refreshes** — *Low*
Good: skip weekend dbt runs (extended Monday lookback); dbt Core state orchestration to skip
unchanged models. Signal: daily-7-day cron on dbt with no weekend handling or state orchestration.
→ Add skipping. (When using state orchestration, never share physical tables across environments —
state is keyed by fully-qualified table name.) Docs: `/docs/guides/reduce-dbt-costs`,
`/docs/guides/dbt-core-state-management`.

**7.4 Cancel redundant task runs** — *Low*
Good: redundant runs cancelled where the integration supports it. Signal: `list_pipeline_runs`
overlaps wasting warehouse compute. → Cancel / set concurrency. Docs:
`/docs/core-concepts/pipelines/pipeline-runs`.

**7.5 Batch programmatic backfills** — *Low* `[MANUAL]`
Good: backfills use the run-multiple-pipelines approach (one token/workspace, rate-limit handling),
not ad-hoc loops. Not directly visible — flag if the user mentions backfill scripts. Docs:
`/docs/guides/run-multiple-pipelines`.

## 8. AI, agents and MCP — *Low* `[MANUAL]`

Mostly configuration/usage guidance not exposed by MCP. If relevant: start from agentic workflow
templates, use the Pipeline AI Agent iteratively (beta — review before publishing), add
human-in-the-loop approvals (`ORCHESTRA APPROVAL` tasks) for production-affecting steps, and connect
one MCP per workspace. Signal you *can* see: production-affecting agent/LLM tasks with no `APPROVAL`
gate. Docs: `/docs/mcp`, `/docs/integrations/orchestra/approval`.

---

## Account-review quick checklist

A scan of the eight conventions that matter most — score each ✅ pass / ⚠️ partial / ❌ fail / —
not assessed. Don't render this list verbatim in the report (the per-area scorecard and findings
table already cover it); use it to drive the **Account health score** (see SKILL.md → Scoring
method): severity-weight each assessed check (High 5 / Medium 3 / Low 1), credit pass=full,
partial=half, fail=0, and score = 100 × Σcredit ÷ Σweight over assessed checks only (`[MANUAL]` and
not-assessed excluded).

1. One pipeline reused across environments, not one per environment. *(1.1, 2.1)*
2. Repeated tasks consolidated into a MetaEngine matrix. *(1.3)*
3. Production pipelines Git-backed and deployed through CI/CD with validation. *(3.1, 3.3, 3.4)*
4. Secrets in a secrets manager or integration credentials, never plain-text vars/params. *(4.3, 4.4)*
5. Granular alerts defined in YAML and routed per domain and environment. *(5.1, 5.2, 5.3)*
6. Pipeline concurrency set where overlapping runs are undesirable. *(1.8)*
7. RBAC roles and groups scoped to least privilege. *(6.1)* `[MANUAL]`
8. Source-tool schedules paused so Orchestra owns orchestration. *(4.5)* `[MANUAL]`
