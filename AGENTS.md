# Agent guide — orchestra-skills

This repository is documentation and workflow instructions for AI agents, not an application runtime. It is distributed as a plugin marketplace with two independently-installable plugins, both listed in the manifests at the repo root (`.claude-plugin/marketplace.json`, `.cursor-plugin/marketplace.json`):

- **`orchestra`** (`skills/orchestra/`) — diagnose/fix/triage pipeline runs, author pipeline YAML, dbt Slim CI, data-quality tests, account health.
- **`migrate-to-orchestra`** (`skills/migrate-to-orchestra/`) — convert pipelines from another orchestrator (Dagster today; Airflow/Prefect planned) into Orchestra pipeline YAML.

Each plugin is a single source of truth for its own skills — no generated copies. Shared Orchestra pipeline/schema material lives under `skills/orchestra/references/orchestra/`, inside the `orchestra` plugin bundle; `migrate-to-orchestra` skills should link to it for schema/validation rules rather than re-deriving their own copy, to avoid two sources of truth drifting apart.

## Choose a skill first

| User intent | Skill | Path |
|-------------|-------|------|
| Author a new pipeline YAML | `create-orchestra-pipeline` | `skills/orchestra/skills/create-orchestra-pipeline/SKILL.md` |
| **Fix anything in a pipeline (entry point)** — identify the failing task and cause, then route | `identify-pipeline-error` | `skills/orchestra/skills/identify-pipeline-error/SKILL.md` |
| Fix a dbt task already identified as a dbt code/config issue | `fix-pipeline-dbt-task` | `skills/orchestra/skills/fix-pipeline-dbt-task/SKILL.md` |
| Fix a Python task already identified as a code/dependency/schema issue | `fix-pipeline-python-task` | `skills/orchestra/skills/fix-pipeline-python-task/SKILL.md` |
| Fix an Orchestra-platform/config issue (or repo code fix with no dedicated skill); retry/explain a failure without a merge gate | `fix-orchestra-pipeline` | `skills/orchestra/skills/fix-orchestra-pipeline/SKILL.md` |
| Prepare a fix on a branch, validate, summarize, and stop for approval | `triage-orchestra-pipeline` | `skills/orchestra/skills/triage-orchestra-pipeline/SKILL.md` |
| Downstream symptom with no obvious pipeline error | `triage-orchestra-pipeline` (symptom-first path) | same |
| Set up dbt Slim CI in Orchestra on an existing production pipeline | `orchestra-dbt-slim-ci-setup` | `skills/orchestra/skills/orchestra-dbt-slim-ci-setup/SKILL.md` |

Read the full `SKILL.md` for the matching skill before changing pipelines, opening pull requests, or calling external APIs.

### Migrating from another orchestrator

Apply `dagster-definitions-to-orchestra` first for any whole-job/whole-`Definitions` conversion — it establishes the pipeline root (`schedule`, `configuration`, `inputs`) that every task-level skill below builds on. All 17 skills live under `skills/migrate-to-orchestra/skills/` and are listed in the [README's Migrate to Orchestra section](README.md#migrate-to-orchestra); they reference each other by bare skill name (e.g. `dagster-alerts-to-orchestra`) since they sit as flat siblings, same as the `orchestra` plugin's skills.

## Reference index

Skill `SKILL.md` files reference shared docs with paths relative to the skill folder (`../../references/orchestra/...`, which resolves to the plugin's `references/orchestra/`). From the repository root, use `skills/orchestra/references/orchestra/`.

| Topic | File |
|-------|------|
| Index | `skills/orchestra/references/orchestra/README.md` |
| YAML authoring schema & validation | `pipeline/yaml-authoring.md` |
| Pipeline pattern examples | `pipeline/examples.md` |
| Failure classification | `pipeline/diagnosis-patterns.md` |
| Remediation actions | `pipeline/remediation-playbooks.md` |
| Past fixes and failure profile | `pipeline/knowledge-store.md` |
| MCP tool names and arguments | `mcp/tools-quick-ref.md` |

## Operating rules

1. **MCP** — Use Orchestra MCP for all operations: listing runs, task runs, logs, artifacts, operations, retries, and reading a pipeline's full definition (`get_pipeline`). The Orchestra MCP server is assumed connected.
2. **Parse input early** — Orchestra UI URLs, bare UUIDs, pipeline aliases, pasted errors, and alert text are all valid entry points; the fix skill documents extraction rules.
3. **Evidence before theory** — Prefer `list_task_run_logs`, `download_task_run_log`, artifacts, and `list_operations` over guessing from status fields alone.
4. **Learning is optional** — Recording fixes is deferred to the calling client's persistent memory; never commit workspace-specific fix history. Add only generic, reusable patterns to `pipeline/diagnosis-patterns.md`.
5. **Triage gate** — The triage skill must not merge to the default branch without explicit user approval (`merge`, `yes`, `approve`, and similar).

## Repository layout

```text
.claude-plugin/
  marketplace.json          # Claude Code marketplace → lists both plugins
.cursor-plugin/
  marketplace.json          # Cursor marketplace → same
skills/
  orchestra/                # plugin bundle: fix/author/audit Orchestra pipelines
    .claude-plugin/plugin.json
    .cursor-plugin/plugin.json
    skills/
      identify-pipeline-error/          # diagnose & fix
      fix-pipeline-dbt-task/
      fix-pipeline-python-task/
      fix-orchestra-pipeline/
      triage-orchestra-pipeline/
      create-orchestra-pipeline/        # author & maintain
      merge-duplicate-pipelines/
      build-data-reconciliation-pipeline/
      account-health-check/             # account health & governance
      orchestra-dbt-slim-ci-setup/      # dbt state-aware orchestration
      configure-dbt-source-freshness/
      configure-dbt-build-after/
      write-snowflake-dq-tests/         # data-quality testing
      write-bigquery-dq-tests/
      write-clickhouse-dq-tests/
      write-databricks-dq-tests/
    references/
      orchestra/            # shared docs, bundled with the plugin
        README.md
        pipeline/
        mcp/
        schemas/
  migrate-to-orchestra/      # plugin bundle: convert other orchestrators to Orchestra
    .claude-plugin/plugin.json
    .cursor-plugin/plugin.json
    skills/
      dagster-definitions-to-orchestra/  # apply first — pipeline root
      dagster-connections-to-orchestra/
      dagster-alerts-to-orchestra/
      dagster-sensors-to-orchestra/
      dagster-cross-job-to-orchestra/
      dagster-branching-to-orchestra/
      dagster-asset-checks-to-orchestra/
      dagster-io-managers-to-orchestra/
      dagster-shell-ssh-to-orchestra/
      dbt-core-dagster-to-orchestra/     # integration/task conversion
      python-dagster-to-orchestra/
      slack-dagster-to-orchestra/
      tableau-dagster-to-orchestra/
      powerbi-dagster-to-orchestra/
      fivetran-dagster-to-orchestra/
      airbyte-cloud-dagster-to-orchestra/
      airbyte-server-dagster-to-orchestra/
      # airflow-*-to-orchestra / prefect-*-to-orchestra planned, same layout
AGENTS.md
README.md
```

## Editing this repository

- Change skill workflows directly in `skills/<plugin>/skills/*/SKILL.md` — each plugin is a single skill tree, no generation step. Write skills client-agnostically: describe a capability ("if your client can schedule a wake-up…") rather than naming a specific tool.
- Change shared playbooks and tool notes under `skills/orchestra/references/orchestra/`. This is the canonical Orchestra pipeline schema/validation source for **both** plugins — if a migration skill needs schema detail (enum values, parameter models), point it here instead of copying a table into `skills/migrate-to-orchestra/`.
- Adding a skill to an existing plugin: create `skills/<plugin>/skills/<name>/SKILL.md`; it is exposed automatically (no manifest edit needed). Bump the `version` in that plugin's `.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`. Also add the skill's path to the `skills` array in `.tessl-plugin/plugin.json` and bump its `version` — `tessl-publish.yml` no longer auto-bumps this on every push (see PR #27), so it now needs the same manual bump as the other two manifests or Tessl publishing silently stops reflecting new skills.
- Adding a new source orchestrator to `migrate-to-orchestra` (Airflow, Prefect, …): add `skills/migrate-to-orchestra/skills/<orchestrator>-*-to-orchestra/` following the existing naming convention — no new plugin or marketplace entry needed, one plugin covers all source orchestrators.
- Adding a genuinely new plugin (a different product surface entirely): create `skills/<new-plugin>/` with its own `.claude-plugin/plugin.json` + `.cursor-plugin/plugin.json`, then add it to the `plugins` array in both root marketplace manifests — `validate-skills.yml`'s "every skill exposed by a plugin" check will fail until both are done.
- Keep user-facing overview in `README.md` and agent routing in this file.
- Never commit secrets or workspace-specific credentials.

## Out of scope

This repo does not ship the Orchestra MCP server implementation, customer pipeline YAML, or integration credentials. Clone [orchestra-mcp](https://github.com/orchestra-hq/orchestra-mcp) and configure MCP separately.
