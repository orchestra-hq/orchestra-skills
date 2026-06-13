# orchestra-skills

Agent skills and reference docs for diagnosing, fixing, and triaging [Orchestra](https://www.getorchestra.io/) data pipelines with an AI assistant. The workflows assume [Orchestra's cloud MCP server](https://docs.getorchestra.io/docs/mcp) is connected so the agent can list runs, fetch logs and artifacts, and retry pipelines from your workspace.

This repo is a **plugin marketplace**: the single `orchestra` plugin bundles every skill and installs into both Claude Code and Cursor from the manifests at the repo root (see [Install](#install-for-humans)).

## What is in this repo

### Skills

Each skill auto-triggers when your prompt matches it — just describe the problem in natural language. The "Try saying" column shows a prompt that activates each one.

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`identify-pipeline-error`](skills/orchestra/skills/identify-pipeline-error/SKILL.md) | **Entry point for fixing anything.** Gets the pipeline run and task runs, identifies which task broke and why, then routes to the right fixer (or handles non-code causes itself). | _"Fix my pipeline"_ / _"what's broken?"_ — or paste a run URL, UUID, or error |
| [`fix-pipeline-dbt-task`](skills/orchestra/skills/fix-pipeline-dbt-task/SKILL.md) | Fixes a dbt Core task once identified as a dbt code/config issue — reproduce, fix in repo, validate on a branch, confirm, merge. Usually invoked by `identify-pipeline-error`. | _"Fix the broken dbt task"_ |
| [`fix-pipeline-python-task`](skills/orchestra/skills/fix-pipeline-python-task/SKILL.md) | Fixes a Python task once identified as a code / dependency / destination-schema issue — edit the script, additive-only schema changes, validate, confirm. Usually invoked by `identify-pipeline-error`. | _"Fix the broken python task"_ |
| [`fix-orchestra-pipeline`](skills/orchestra/skills/fix-orchestra-pipeline/SKILL.md) | Fixes an Orchestra-platform/configuration issue (YAML/inputs/ordering/retry) or a repo code fix in an integration with no dedicated skill — apply fix, PR/poll, retry, confirm. Usually invoked by `identify-pipeline-error`. | _"The pipeline config is wrong, fix it"_ |
| [`triage-orchestra-pipeline`](skills/orchestra/skills/triage-orchestra-pipeline/SKILL.md) | Same diagnosis, but opens a fix PR and validates it on a branch, then **stops for your approval** before merging. | _"Triage my pipeline but don't merge yet"_ |
| [`account-health-check`](skills/orchestra/skills/account-health-check/SKILL.md) | Read-only audit of your Orchestra workspace against best practices — findings grouped by area with severity, evidence, and fixes, written to a report plus chat summary. Never edits anything. | _"Audit my Orchestra account / is my setup following best practices?"_ |
| [`merge-duplicate-pipelines`](skills/orchestra/skills/merge-duplicate-pipelines/SKILL.md) | Finds pipelines that are the same process duplicated per environment or conceptually (per customer/region), drafts a consolidated pipeline using Environment overlays/inputs/matrices, and asks per duplicate set before creating, PR-ing, or pausing anything. | _"Why do I have three copies of this pipeline? Consolidate them."_ |
| [`create-orchestra-pipeline`](skills/orchestra/skills/create-orchestra-pipeline/SKILL.md) | Author, validate, and remediate a `version: v1` pipeline YAML from a description. | _"Create a pipeline that runs dbt then loads Snowflake"_ |
| [`orchestra-dbt-slim-ci-setup`](skills/orchestra/skills/orchestra-dbt-slim-ci-setup/SKILL.md) | Retrofit dbt Slim CI (`run-pipeline`, `latest_production`, `state:modified+`, `--defer`) onto an existing production dbt pipeline. | _"Set up dbt Slim CI in Orchestra"_ |
| [`run-snowflake-quality-tests`](skills/orchestra/skills/run-snowflake-quality-tests/SKILL.md) | Inspect Snowflake tables, then build and deploy a data-quality testing pipeline to Orchestra. | _"Run Snowflake data quality tests"_ |
| [`configure-dbt-source-freshness`](skills/orchestra/skills/configure-dbt-source-freshness/SKILL.md) | Author dbt source freshness (warehouse-correct `loaded_at_field`/thresholds) and enable `use_state_orchestration` so Orchestra skips downstream models when sources are unchanged. | _"Set up source freshness for state-aware orchestration"_ |
| [`configure-dbt-build-after`](skills/orchestra/skills/configure-dbt-build-after/SKILL.md) | Author per-model `build_after` (SLA + upstream-freshness gating) so Orchestra rebuilds a model only when it's due and its data is fresh. | _"Make my marts state-aware — only rebuild when due and fresh"_ |

**To get going:** connect [Orchestra's cloud MCP server](https://docs.getorchestra.io/docs/mcp) (see [Install](#install-for-humans) below), install the `orchestra` plugin so the skills are discoverable by your client (see Install), then just ask.

### Reference library

Start at [`skills/orchestra/references/orchestra/README.md`](skills/orchestra/references/orchestra/README.md). Highlights:

- **Pipeline** — authoring schema + examples, failure classification, remediation playbooks, and an optional local fix-history template ([`knowledge-store.md`](skills/orchestra/references/orchestra/pipeline/knowledge-store.md))
- **State-aware orchestration (dbt SAO)** — source-freshness and `build_after` schemas, enabling `use_state_orchestration`, and a per-warehouse freshness matrix for Snowflake, BigQuery, Databricks, MotherDuck/DuckDB, Redshift, Microsoft Fabric, and Postgres (plus an `other` fallback) ([`dbt-sao/`](skills/orchestra/references/orchestra/dbt-sao/README.md))
- **MCP** — [cloud MCP](https://docs.getorchestra.io/docs/mcp) setup and tool quick reference

## Install for humans

### Prerequisites

- An Orchestra API key (Orchestra UI → Settings → API Keys)

1. **Connect Orchestra's cloud MCP server.** Point your client at the hosted endpoint following the [cloud MCP docs](https://docs.getorchestra.io/docs/mcp) (`~/.claude/mcp.json` for Claude Code, or Cursor MCP settings) and authenticate with your `ORCHESTRA_API_KEY` — no local install required. Restart/reload so tools such as `list_pipeline_runs` and `list_task_run_logs` appear.
2. **Install the `orchestra` plugin** so the skills are discoverable by your client:
   - **Claude Code** — add this repo as a marketplace, then install the plugin:
     ```
     /plugin marketplace add orchestra-hq/orchestra-skills
     /plugin install orchestra@orchestra-marketplace
     ```
     (or point at a local clone: `/plugin marketplace add /path/to/orchestra-skills`).
   - **Cursor** — add the marketplace and install the `orchestra` plugin from `.cursor-plugin/marketplace.json` per [Cursor's plugin docs](https://docs.cursor.com/).
   Each skill auto-triggers from a matching prompt once installed.
3. For agent behavior in this repo, read [`AGENTS.md`](AGENTS.md).

## Typical workflows

**Failed run** — Paste a pipeline run URL, run UUID, pipeline name, or error snippet. `identify-pipeline-error` parses the input, loads the pipeline run and failed task runs, identifies the failing task and its cause, then routes to the right fixer: a dbt code issue → `fix-pipeline-dbt-task`, a Python code/schema issue → `fix-pipeline-python-task`, an Orchestra-platform/config issue → `fix-orchestra-pipeline`. Data, vendor/ingestion, auth, network, and other causes are reported with the right next action by `identify-pipeline-error` itself.

**Author pipeline YAML** — Describe the desired stages/tasks and create a `version: v1` pipeline YAML. The authoring skill validates (via `orchestra-cli` or MCP) and remediates validation errors until clean.

**Review before merge** — Use the triage skill when you want a branch fix, validation run, and triage summary, then explicit approval before merge and production retry.

**Downstream symptom** — Triage can start from a downstream issue (stale dashboard, bad dbt output) and walk upstream through the pipeline graph.

## Contributing

- Skills live under [`skills/orchestra/skills/`](skills/orchestra/skills/) and shared Orchestra material under [`skills/orchestra/references/orchestra/`](skills/orchestra/references/orchestra/), all inside the single `orchestra` plugin bundle. There is a single skill tree — no generated copies to keep in sync.
- To add a skill, create `skills/orchestra/skills/<skill-name>/SKILL.md` with `name` + `description` frontmatter, put any supporting `references/`/`templates/` in the same folder, and add it to the [Skills](#skills) table. The `orchestra` plugin exposes it automatically — bump the `version` in `skills/orchestra/.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`. CI (`Validate Skills`) checks the frontmatter, that `SKILL.md` stays under ~500 lines, and that the manifests are valid JSON. Write skills to be client-agnostic — describe capabilities (e.g. "if your client can schedule a wake-up…") rather than naming a specific tool.
- Recording fixes is optional and deferred to your client's persistent memory — never commit workspace-specific fix history. Extend [`pipeline/diagnosis-patterns.md`](skills/orchestra/references/orchestra/pipeline/diagnosis-patterns.md) only with generic, reusable patterns.
- **Evals.** Skill evals live under [`evals/`](evals/) — an eval-driven harness that runs a skill with and without it via the headless `claude` CLI and grades the output. Currently wired up for `run-snowflake-quality-tests`. See [`evals/README.md`](evals/README.md) for setup and how to run, grade, and add a suite.
- Do not commit API keys, `.env` files, or other secrets.

Agents editing this repo should follow [`AGENTS.md`](AGENTS.md).
