# orchestra-skills

Agent skills and reference docs for diagnosing, fixing, and triaging [Orchestra](https://www.getorchestra.io/) data pipelines with an AI assistant. The workflows assume [Orchestra's cloud MCP server](https://docs.getorchestra.io/docs/mcp) is connected so the agent can list runs, fetch logs and artifacts, and retry pipelines from your workspace.

This repo is a **plugin marketplace** with two plugins, installed independently into both Claude Code and Cursor from the manifests at the repo root (see [Install](#install-for-humans)):

- **`orchestra`** — diagnose/fix/triage runs, author pipeline YAML, dbt Slim CI, data-quality tests, account health.
- **`migrate-to-orchestra`** — convert pipelines from another orchestrator (Dagster today; Airflow and Prefect are planned) into Orchestra pipeline YAML.

## What is in this repo

### Skills

Each skill auto-triggers when your prompt matches it — just describe the problem in natural language. The "Try saying" column shows a prompt that activates each one. Skills are grouped below by what they're for.

#### Diagnose & fix pipelines

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`identify-pipeline-error`](skills/orchestra/skills/identify-pipeline-error/SKILL.md) | **Entry point for fixing anything.** Gets the pipeline run and task runs, identifies which task broke and why, then routes to the right fixer (or handles non-code causes itself). | _"Fix my pipeline"_ / _"what's broken?"_ — or paste a run URL, UUID, or error |
| [`fix-pipeline-dbt-task`](skills/orchestra/skills/fix-pipeline-dbt-task/SKILL.md) | Fixes a dbt Core task once identified as a dbt code/config issue — reproduce, fix in repo, validate on a branch, confirm, merge. Usually invoked by `identify-pipeline-error`. | _"Fix the broken dbt task"_ |
| [`fix-pipeline-python-task`](skills/orchestra/skills/fix-pipeline-python-task/SKILL.md) | Fixes a Python task once identified as a code / dependency / destination-schema issue — edit the script, additive-only schema changes, validate, confirm. Usually invoked by `identify-pipeline-error`. | _"Fix the broken python task"_ |
| [`fix-orchestra-pipeline`](skills/orchestra/skills/fix-orchestra-pipeline/SKILL.md) | Fixes an Orchestra-platform/configuration issue (YAML/inputs/ordering/retry) or a repo code fix in an integration with no dedicated skill — apply fix, PR/poll, retry, confirm. Usually invoked by `identify-pipeline-error`. | _"The pipeline config is wrong, fix it"_ |
| [`triage-orchestra-pipeline`](skills/orchestra/skills/triage-orchestra-pipeline/SKILL.md) | Same diagnosis, but opens a fix PR and validates it on a branch, then **stops for your approval** before merging. | _"Triage my pipeline but don't merge yet"_ |

#### Author & maintain pipelines

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`create-orchestra-pipeline`](skills/orchestra/skills/create-orchestra-pipeline/SKILL.md) | Author, validate, and remediate a `version: v1` pipeline YAML from a description; also handles edits to an existing pipeline. | _"Create a pipeline that runs dbt then loads Snowflake"_ |
| [`merge-duplicate-pipelines`](skills/orchestra/skills/merge-duplicate-pipelines/SKILL.md) | Finds pipelines that are the same process duplicated per environment or conceptually (per customer/region), drafts a consolidated pipeline using Environment overlays/inputs/matrices, and asks per duplicate set before creating, PR-ing, or pausing anything. | _"Why do I have three copies of this pipeline? Consolidate them."_ |
| [`build-data-reconciliation-pipeline`](skills/orchestra/skills/build-data-reconciliation-pipeline/SKILL.md) | Builds a pipeline using Orchestra's native Data Reconciliation tasks to prove two systems (Snowflake/SQL Server/Databricks) match — a full validation check for migration cutover, plus an optional scheduled cursor-field drift monitor afterward. | _"Make sure our Snowflake-to-Databricks migration matches before we cut over."_ |

#### Account health & governance

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`account-health-check`](skills/orchestra/skills/account-health-check/SKILL.md) | Read-only audit of your Orchestra workspace against best practices — findings grouped by area with severity, evidence, and fixes, written to a report plus chat summary. Never edits anything. | _"Audit my Orchestra account / is my setup following best practices?"_ |

#### dbt state-aware orchestration

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`orchestra-dbt-slim-ci-setup`](skills/orchestra/skills/orchestra-dbt-slim-ci-setup/SKILL.md) | Retrofit dbt Slim CI (`run-pipeline`, `latest_production`, `state:modified+`, `--defer`) onto an existing production dbt pipeline. | _"Set up dbt Slim CI in Orchestra"_ |
| [`configure-dbt-source-freshness`](skills/orchestra/skills/configure-dbt-source-freshness/SKILL.md) | Author dbt source freshness (warehouse-correct `loaded_at_field`/thresholds) and enable `use_state_orchestration` so Orchestra skips downstream models when sources are unchanged. | _"Set up source freshness for state-aware orchestration"_ |
| [`configure-dbt-build-after`](skills/orchestra/skills/configure-dbt-build-after/SKILL.md) | Author per-model `build_after` (SLA + upstream-freshness gating) so Orchestra rebuilds a model only when it's due and its data is fresh. | _"Make my marts state-aware — only rebuild when due and fresh"_ |

#### Data-quality testing

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`write-snowflake-dq-tests`](skills/orchestra/skills/write-snowflake-dq-tests/SKILL.md) | Profile Snowflake data, design tests that fit what each column actually means, then build and deploy a DQ testing pipeline to Orchestra. | _"Write data quality tests for my Snowflake tables"_ |
| [`write-bigquery-dq-tests`](skills/orchestra/skills/write-bigquery-dq-tests/SKILL.md) | Same profile-then-test workflow as above, for BigQuery. | _"Write data quality tests for my BigQuery tables"_ |
| [`write-clickhouse-dq-tests`](skills/orchestra/skills/write-clickhouse-dq-tests/SKILL.md) | Same profile-then-test workflow as above, for ClickHouse. | _"Write data quality tests for my ClickHouse tables"_ |
| [`write-databricks-dq-tests`](skills/orchestra/skills/write-databricks-dq-tests/SKILL.md) | Same profile-then-test workflow as above, for Databricks. | _"Write data quality tests for my Databricks tables"_ |

**To get going:** connect [Orchestra's cloud MCP server](https://docs.getorchestra.io/docs/mcp) (see [Install](#install-for-humans) below), install the `orchestra` plugin so the skills are discoverable by your client (see Install), then just ask.

### Migrate to Orchestra

A separate plugin (`migrate-to-orchestra`) for converting pipelines from another orchestrator into Orchestra pipeline YAML. Point your client at the source project (Dagster or Prefect code today) and describe what you want migrated — each skill auto-triggers off the APIs it recognizes. Start with `dagster-definitions-to-orchestra` (Dagster) or `prefect-flow-structure-to-orchestra` (Prefect) for any whole-job/whole-flow conversion; it establishes the pipeline root that the task-level skills below build on.

_Not yet in `.tessl-plugin/plugin.json` — intentionally excluded from Tessl publishing for now._

#### Pipeline structure & cross-cutting concerns

| Skill | What it does |
|-------|--------------|
| [`dagster-definitions-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-definitions-to-orchestra/SKILL.md) | Converts `Definitions`/`ScheduleDefinition`/`RetryPolicy`/concurrency/`Config` into the Orchestra pipeline root (`schedule`, `configuration`, `inputs`). Apply first, before any task-level skill. |
| [`dagster-connections-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-connections-to-orchestra/SKILL.md) | Maps Dagster resources (`ConfigurableResource`, `SnowflakeResource`, `EnvVar`, etc.) to Orchestra connections and naming/secrets conventions. |
| [`dagster-alerts-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-alerts-to-orchestra/SKILL.md) | Converts run-failure/status sensors and success/failure hooks into Orchestra's `alerts:` block across all six destination types. |
| [`dagster-sensors-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-sensors-to-orchestra/SKILL.md) | Converts `@sensor`/`@asset_sensor`/`@multi_asset_sensor` polling external state into Orchestra `sensors:`. |
| [`dagster-cross-job-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-cross-job-to-orchestra/SKILL.md) | Converts cross-job/cross-code-location triggers (`@run_status_sensor` yielding `RunRequest`, `@asset_sensor` on another job's asset) into Orchestra pipeline-triggers-pipeline patterns. |
| [`dagster-branching-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-branching-to-orchestra/SKILL.md) | Converts conditional op branching, `DynamicOut` fan-out, and conditional asset materialization into Orchestra `condition:`/matrix patterns. |
| [`dagster-asset-checks-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-asset-checks-to-orchestra/SKILL.md) | Converts `@asset_check`/`AssetCheckResult`/dbt-test-via-`dagster-dbt`/`ExpectationResult` into Orchestra DQ test tasks. |
| [`dagster-io-managers-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-io-managers-to-orchestra/SKILL.md) | Converts op/asset return values, `Out`/`In` wiring, and IO managers into Orchestra task `OUTPUTS`/`${{ }}` data passing. |
| [`dagster-shell-ssh-to-orchestra`](skills/migrate-to-orchestra/skills/dagster-shell-ssh-to-orchestra/SKILL.md) | Converts non-dbt shell/container execution (`PipesSubprocessClient`, `dagster-shell`, `SSHResource`, `k8s_job_op`) into Orchestra `LINUX_SSH`/container tasks. |

#### Integration & task conversion

| Skill | What it does |
|-------|--------------|
| [`dbt-core-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/dbt-core-dagster-to-orchestra/SKILL.md) | Converts `DbtCliResource`/`@dbt_assets`/`dagster-dbt` into an Orchestra `DBT_CORE` task. |
| [`python-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/python-dagster-to-orchestra/SKILL.md) | Converts plain `@op`/`@asset` Python logic (pandas, boto3, API calls) into an Orchestra `PYTHON` task. |
| [`slack-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/slack-dagster-to-orchestra/SKILL.md) | Converts `SlackResource` and Slack-posting hooks/sensors into an Orchestra `SLACK` alert or task. |
| [`tableau-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/tableau-dagster-to-orchestra/SKILL.md) | Converts `TableauCloudWorkspace`/`TableauServerWorkspace` asset materialization into an Orchestra `TABLEAU_CLOUD` task. |
| [`powerbi-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/powerbi-dagster-to-orchestra/SKILL.md) | Converts `PowerBIWorkspace`/semantic-model refresh assets into an Orchestra `POWER_BI` task. |
| [`fivetran-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/fivetran-dagster-to-orchestra/SKILL.md) | Converts `FivetranResource`/`FivetranWorkspace` assets into an Orchestra `FIVETRAN` task. |
| [`airbyte-cloud-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/airbyte-cloud-dagster-to-orchestra/SKILL.md) | Converts `AirbyteCloudResource` assets into an Orchestra `AIRBYTE_CLOUD` task. |
| [`airbyte-server-dagster-to-orchestra`](skills/migrate-to-orchestra/skills/airbyte-server-dagster-to-orchestra/SKILL.md) | Converts self-hosted `AirbyteResource(host=,port=)` assets into an Orchestra `AIRBYTE_SERVER` task. |

#### Prefect

| Skill | What it does |
|-------|--------------|
| [`prefect-flow-structure-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-flow-structure-to-orchestra/SKILL.md) | Converts `@flow`/`CronSchedule`/`retries`/typed parameters into the Orchestra pipeline root (`schedule`, `configuration`, `inputs`). Apply first, before any task-level skill. |
| [`prefect-connections-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-connections-to-orchestra/SKILL.md) | Maps Prefect blocks (`SnowflakeCredentials`, `AwsCredentials`, `SlackWebhook`, etc.) to Orchestra connections and naming/secrets conventions. |
| [`prefect-alerts-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-alerts-to-orchestra/SKILL.md) | Converts `on_failure`/`on_completion` hooks and Prefect Automation notification actions into Orchestra's `alerts:` block across all six destination types. |
| [`prefect-automations-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-automations-to-orchestra/SKILL.md) | Converts Automations reacting to external events (storage events, DB polling, webhooks) into Orchestra `sensors:`/`webhook:`. |
| [`prefect-cross-flow-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-cross-flow-to-orchestra/SKILL.md) | Converts `run_deployment()` calls and subflows into Orchestra `trigger_events:` pipeline-triggers-pipeline patterns. |
| [`prefect-conditions-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-conditions-to-orchestra/SKILL.md) | Converts input-driven and runtime output-driven branching, plus `allow_failure`, into Orchestra `condition:` expressions. |
| [`prefect-testing-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-testing-to-orchestra/SKILL.md) | Converts `@task`-based SQL assertions, Great Expectations, and Soda checks into Orchestra DQ test tasks (with the Prefect-pass/Orchestra-fail semantic inversion). |
| [`prefect-data-passing-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-data-passing-to-orchestra/SKILL.md) | Converts implicit return-value passing, `.submit()` futures, and `.map()` fan-out into Orchestra `set_outputs`/`OUTPUTS`/matrix patterns. |
| [`prefect-secrets-to-orchestra`](skills/migrate-to-orchestra/skills/prefect-secrets-to-orchestra/SKILL.md) | Produces a secrets checklist from `Secret`/`SecretStr`/`SecretDict` usage — never asks for or writes real secret values. |

#### Integration & task conversion (Prefect)

| Skill | What it does |
|-------|--------------|
| [`dbt-core-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/dbt-core-prefect-to-orchestra/SKILL.md) | Converts `DbtCoreOperation`/`ShellOperation`/`DbtCloudJob` into an Orchestra `DBT_CORE` or `DBT` task. |
| [`python-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/python-prefect-to-orchestra/SKILL.md) | Converts plain `@task` Python logic (pandas, boto3, API calls) into an Orchestra `PYTHON` task. |
| [`slack-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/slack-prefect-to-orchestra/SKILL.md) | Converts `SlackWebhook`/hooks/raw `slack_sdk` calls into an Orchestra `SLACK` alert or task. |
| [`tableau-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/tableau-prefect-to-orchestra/SKILL.md) | Converts hand-rolled `tableau-server-client` refresh tasks into an Orchestra `TABLEAU_CLOUD` task. |
| [`powerbi-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/powerbi-prefect-to-orchestra/SKILL.md) | Converts hand-rolled `msal`+`requests` Power BI refresh tasks into an Orchestra `POWER_BI` task. |
| [`fivetran-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/fivetran-prefect-to-orchestra/SKILL.md) | Converts `FivetranConnector` sync tasks into an Orchestra `FIVETRAN` task. |
| [`airbyte-cloud-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/airbyte-cloud-prefect-to-orchestra/SKILL.md) | Converts `AirbyteConnection` tasks pointed at `api.airbyte.com` into an Orchestra `AIRBYTE_CLOUD` task. |
| [`airbyte-server-prefect-to-orchestra`](skills/migrate-to-orchestra/skills/airbyte-server-prefect-to-orchestra/SKILL.md) | Converts `AirbyteConnection` tasks pointed at a self-hosted host into an Orchestra `AIRBYTE_SERVER` task. |

**To get going:** install the `migrate-to-orchestra` plugin (see [Install](#install-for-humans)), open a Claude/Cursor session in the source Dagster or Prefect project, and describe the migration — no upload step needed, the skills read the project's own source files directly.

### Reference library

Start at [`skills/orchestra/references/orchestra/README.md`](skills/orchestra/references/orchestra/README.md). Highlights:

- **Pipeline** — authoring schema + examples, failure classification, remediation playbooks, and an optional local fix-history template ([`knowledge-store.md`](skills/orchestra/references/orchestra/pipeline/knowledge-store.md))
- **State-aware orchestration (dbt SAO)** — source-freshness and `build_after` schemas, enabling `use_state_orchestration`, and a per-warehouse freshness matrix for Snowflake, BigQuery, Databricks, MotherDuck/DuckDB, Redshift, Microsoft Fabric, and Postgres (plus an `other` fallback) ([`dbt-sao/`](skills/orchestra/references/orchestra/dbt-sao/README.md))
- **MCP** — [cloud MCP](https://docs.getorchestra.io/docs/mcp) setup and tool quick reference

## Install for humans

### Prerequisites

- An Orchestra API key (Orchestra UI → Settings → API Keys)

1. **Connect Orchestra's cloud MCP server.** Point your client at the hosted endpoint following the [cloud MCP docs](https://docs.getorchestra.io/docs/mcp) (`~/.claude/mcp.json` for Claude Code, or Cursor MCP settings) and authenticate with your `ORCHESTRA_API_KEY` — no local install required. Restart/reload so tools such as `list_pipeline_runs` and `list_task_run_logs` appear.
2. **Install the plugin(s) you need** so the skills are discoverable by your client — the two install independently:
   - **Claude Code** — add this repo as a marketplace, then install one or both plugins:
     ```
     /plugin marketplace add orchestra-hq/orchestra-skills
     /plugin install orchestra@orchestra-marketplace
     /plugin install migrate-to-orchestra@orchestra-marketplace
     ```
     (or point at a local clone: `/plugin marketplace add /path/to/orchestra-skills`).
   - **Cursor** — add the marketplace and install `orchestra` and/or `migrate-to-orchestra` from `.cursor-plugin/marketplace.json` per [Cursor's plugin docs](https://docs.cursor.com/).
   Each skill auto-triggers from a matching prompt once installed.
3. For agent behavior in this repo, read [`AGENTS.md`](AGENTS.md).

## Typical workflows

**Failed run** — Paste a pipeline run URL, run UUID, pipeline name, or error snippet. `identify-pipeline-error` parses the input, loads the pipeline run and failed task runs, identifies the failing task and its cause, then routes to the right fixer: a dbt code issue → `fix-pipeline-dbt-task`, a Python code/schema issue → `fix-pipeline-python-task`, an Orchestra-platform/config issue → `fix-orchestra-pipeline`. Data, vendor/ingestion, auth, network, and other causes are reported with the right next action by `identify-pipeline-error` itself.

**Author pipeline YAML** — Describe the desired stages/tasks and create a `version: v1` pipeline YAML. The authoring skill validates (via `orchestra-cli` or MCP) and remediates validation errors until clean.

**Review before merge** — Use the triage skill when you want a branch fix, validation run, and triage summary, then explicit approval before merge and production retry.

**Downstream symptom** — Triage can start from a downstream issue (stale dashboard, bad dbt output) and walk upstream through the pipeline graph.

## Contributing

- Skills live under [`skills/orchestra/skills/`](skills/orchestra/skills/) (the `orchestra` plugin) and [`skills/migrate-to-orchestra/skills/`](skills/migrate-to-orchestra/skills/) (the `migrate-to-orchestra` plugin), each its own plugin bundle with its own `.claude-plugin/plugin.json`/`.cursor-plugin/plugin.json`. Shared Orchestra pipeline/schema material lives under [`skills/orchestra/references/orchestra/`](skills/orchestra/references/orchestra/) and is the single source of truth for pipeline YAML schema/validation — migration skills should link to it rather than re-deriving schema tables locally, to avoid two sources drifting apart.
- To add a skill, create `skills/<plugin>/skills/<skill-name>/SKILL.md` with `name` + `description` frontmatter, put any supporting `references/`/`templates/` in the same folder, and add it to the relevant category table under [Skills](#skills) (or [Migrate to Orchestra](#migrate-to-orchestra)). The plugin exposes it automatically — bump the `version` in that plugin's `.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`. Also add its path to the `skills` array in `.tessl-plugin/plugin.json` and bump its `version` — this isn't auto-generated, so a skill left out here silently stops showing up in Tessl's published listing (Tessl has no plugin concept, so both plugins show up in one flat list there — the `skills/<plugin>/...` path prefix is the only separation). CI (`Validate Skills`) checks the frontmatter, that `SKILL.md` stays under ~500 lines, that the manifests are valid JSON, and that every skill on disk lives inside some plugin's `skills/` directory. Write skills to be client-agnostic — describe capabilities (e.g. "if your client can schedule a wake-up…") rather than naming a specific tool.
- To add a new orchestrator's migration skills (Airflow, …) alongside Dagster's and Prefect's, add them under `skills/migrate-to-orchestra/skills/<orchestrator>-*-to-orchestra/` following the existing naming convention — one plugin covers all source orchestrators, so no new plugin/marketplace entry is needed. If a shared/reused skill from another orchestrator's set (e.g. a `connections`-style skill) doesn't have a same-orchestrator equivalent, author a new one rather than pointing the new orchestrator's skills at another orchestrator's vocabulary.
- Recording fixes is optional and deferred to your client's persistent memory — never commit workspace-specific fix history. Extend [`pipeline/diagnosis-patterns.md`](skills/orchestra/references/orchestra/pipeline/diagnosis-patterns.md) only with generic, reusable patterns.
- **Evals.** Skill evals live under [`evals/`](evals/) — an eval-driven harness that runs a skill with and without it via the headless `claude` CLI and grades the output. Currently wired up for `write-snowflake-dq-tests`. See [`evals/README.md`](evals/README.md) for setup and how to run, grade, and add a suite.
- Do not commit API keys, `.env` files, or other secrets.

Agents editing this repo should follow [`AGENTS.md`](AGENTS.md).
