---
name: account-health-check
description: >
  Audit an Orchestra workspace for best practices — git control, secret/env
  hygiene, alerting coverage, security (SSO/RBAC), metadata/lineage, repeated
  tasks (MetaEngine), auto-fix agents, and hybrid-deployment fit — and emit a
  scored report with concrete, doc-linked recommendations.
disable-model-invocation: true
---

A **read-only** audit. Gather, don't change. Narrate briefly like a data engineer; never print secrets. End with a scorecard and prioritised recommendations, each with a docs link.

## 0. Access

Use the Orchestra MCP if connected (`list_pipelines`, `list_task_runs`, etc.). If it isn't, fall back to the public REST API with `$ORCHESTRA_API_KEY` (often already in the env); for reading git-backed YAMLs, `$GITHUB_TOKEN`.
If neither MCP nor a key is available, walk the user through `../../../references/orchestra/mcp/setup.md` and stop. **Recommend connecting the MCP regardless** — it makes every future fix/triage skill work.

REST base: `https://app.getorchestra.io/api/engine/public` — header `Authorization: Bearer $ORCHESTRA_API_KEY`.

## 1. Inventory the pipelines

`list_pipelines` (MCP) or `GET /pipelines`. For each, capture `name`, `id/alias`, `storageProvider`, and the env(s) it runs in. Then read each definition:
- **Git-backed** (`storageProvider: GITHUB`): read the YAML from the repo (`orchestra/*.yml`).
- **Orchestra-backed**: get the definition from the MCP/API.

You'll run the checks below against the full set of definitions.

## 2. Checks

For each, state coverage as `N/total pipelines` and give the fix + doc link.

### A. Git control
**Rule:** every pipeline should be git-backed (`storageProvider: GITHUB`).
If any are Orchestra-backed, recommend moving them to git for version control, PRs, CI, and so the fix/triage skills can hotfix them. → [Git Control](https://docs.getorchestra.io/docs/git-control-and-ci-cd/git-control)

### B. Secret / env hygiene in connections
**Rule:** `connection:` and credential-bearing params should reference `${{ ENV.VAR }}` (or a named connection), **never** hardcoded ids, account names, or secrets inline.
Flag any literal connection strings/ids/tokens in YAML. Recommend `${{ ENV.* }}` so the same definition is portable across dev/prod and nothing sensitive sits in git. → [Connections & Credential Management](https://docs.getorchestra.io/docs/core-concepts/tasks/connections)

### C. Alerting coverage
**Rule:** every pipeline has an `alerts:` block firing on failure (and ideally `RUNNING_TIMEOUT`) to a real destination (Slack/Teams/PagerDuty/email).
List pipelines with **no** alerts, or alerts that don't cover `FAILED`. Recommend adding alerts everywhere — a silent failure is the worst failure.
```yaml
alerts:
- name: On Failure
  statuses: [FAILED, RUNNING_TIMEOUT]
  destinations: [{ integration: SLACK, destination: '#data-alerts' }]
```
→ [Slack](https://docs.getorchestra.io/docs/alerts/slack) · [PagerDuty](https://docs.getorchestra.io/docs/alerts/pagerduty) · [Email](https://docs.getorchestra.io/docs/alerts/email) · [Datadog](https://docs.getorchestra.io/docs/alerts/datadog)

### D. Repeated tasks → MetaEngine
**Rule:** when a pipeline repeats near-identical tasks differing only by a parameter (e.g. many `FIVETRAN_SYNC_ALL` with different `connector_id`, or dbt runs per source), it should use a MetaEngine `matrix` (a "for-each") instead of copy-paste.
Detect: ≥3 tasks in one definition sharing `integration` + `integration_job` and differing only in one param. Recommend collapsing to a matrix — one definition, automatic per-item task IDs, controllable parallelism, inputs that can resolve from upstream outputs.
```yaml
matrix:
  inputs:
    connectors: [conn_1, conn_2, conn_3]
# reference as ${{ MATRIX.connectors }}
```
→ [MetaEngine Tasks](https://docs.getorchestra.io/docs/core-concepts/tasks/metaengine)

### E. Metadata / lineage enabled (dbt, dbt Cloud, Coalesce)
**Rule:** transformation tasks should emit metadata so Orchestra builds lineage and data assets.
- **dbt Core**: confirm `manifest.json` + `run_results.json` artifacts are produced/uploaded (and state orchestration where used). Without them there's no lineage.
- **dbt Cloud jobs** and **Coalesce jobs**: confirm metadata collection is enabled on the integration/connection.
Flag any transform task with metadata off and recommend enabling it — lineage, column-level impact, and the triage skills all depend on it. → [dbt metadata/artifacts](https://docs.getorchestra.io/docs/guides/dbt-core/gha-setup) · [Metadata API](https://docs.getorchestra.io/docs/api)

### F. Security — SSO & RBAC
**Rule:** workspace should have SSO and RBAC configured (and consider IP restrictions).
This is account-level (not visible in pipeline YAML) — surface it as a standing recommendation: enforce SSO, assign least-privilege roles, scope connections per role. → [Security & Data Protection](https://docs.getorchestra.io/docs/deployment-options/security)

### G. Auto-fix AI agents
**Rule:** recommend setting up AI agents/agentic pipelines that can triage and auto-fix failures (the same flows as the `fix-pipeline-*` / `triage-orchestra-pipeline` skills), so common breakages self-heal or arrive pre-diagnosed. → [AI Agent pipelines](https://docs.getorchestra.io/docs/core-concepts/pipelines/ai_agent) · [Agentic Workflow Templates](https://docs.getorchestra.io/docs/ai_agents)

### H. Hybrid-deployment fit (Python-heavy workloads)
**Rule:** if the account runs a lot of Python compute, hybrid deployment (compute in the customer's own environment, control plane in Orchestra) is often better for cost, scale, and data-residency/security.
Measure it — pull recent Python task runs and total their duration:
```
GET /task_runs?integration=PYTHON&page_size=200&time_from=<ISO>&time_to=<ISO>
# sum (completedAt - startedAt); also note count, max memory/cpu params, frequency
```
If Python compute is a large/long share of runs (e.g. many long-running or high-memory tasks), recommend evaluating hybrid (and self-hosted tasks). Quantify in the report ("Python tasks = X runs, Y total minutes/week"). → [Hybrid Deployment](https://docs.getorchestra.io/docs/deployment-options/hybrid/) · [Architecture & Security](https://docs.getorchestra.io/docs/deployment-options/hybrid/architecture) · [Self-hosted Tasks](https://docs.getorchestra.io/docs/core-concepts/tasks/self-hosted-tasks/)

### I. Other helpful checks (opportunistic)
- **Schedules & timezones**: pipelines with no schedule and no webhook/trigger may be orphaned; cron should be Quartz 6-field.
- **No-PR / direct-to-main**: git-backed pipelines without CI (Slim CI) — point to the `orchestra-dbt-slim-ci-setup` skill.
- **Reliability**: from `list_task_runs`, flag tasks with a high recent failure rate or frequent timeouts (candidates for retries/compute bump).
- **Stale connections / unused pipelines**: never-run or long-idle pipelines.
- **Approval gates** on production-writing/destructive steps.

## 3. Report

Lead with a one-line health grade, then the scorecard, then prioritised actions.

```
## Orchestra Account Health — <workspace>  (<date>)
Overall: <🟢 healthy / 🟡 needs attention / 🔴 at risk>

| Check                       | Status | Coverage      |
|-----------------------------|--------|---------------|
| Git control                 | 🟢/🟡/🔴 | 8/10 git-backed |
| Env vars in connections     |        | 2 pipelines hardcode ids |
| Alerting coverage           |        | 6/10 have failure alerts |
| MetaEngine for repeats      |        | 3 pipelines repeat tasks |
| Metadata/lineage enabled    |        | dbt ✓, Coalesce ✗ |
| SSO & RBAC                  |        | recommend |
| Auto-fix agents             |        | not set up |
| Hybrid fit (Python load)    |        | Python = N runs / M min/wk |

### Top recommendations (priority order)
1. <highest-impact gap> — <one line> → <doc link>
2. ...
```

Sort recommendations by risk/impact (silent-failure alerting and leaked secrets first). Offer to action the fixable ones (e.g. add `alerts:` blocks, convert to MetaEngine, swap hardcoded ids for `${{ ENV.* }}`) via the relevant skill — but only on request; this skill itself only reports.

## Notes
- Read-only: never edit pipelines, connections, or settings during the audit.
- Don't print secrets you find — report "hardcoded credential in `<file>`", not the value.
- Mind the 7-day metadata window and pagination; batch `list_*` calls.
- SSO/RBAC/hybrid are account-level — recommend with links rather than trying to detect from YAML.
