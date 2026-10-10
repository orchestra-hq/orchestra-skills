---
name: orchestra-dbt-slim-ci-setup
description: Retrofits dbt Slim CI onto an existing Orchestra production dbt pipeline using latest_production, state:modified+, and --defer, with GitHub Actions run-pipeline as the primary CI trigger. Use when setting up Orchestra Slim CI, dbt CI/CD in Orchestra, run-pipeline for dbt, or latest_production defer state in a dbt repo or from outside it.
---

# Orchestra dbt Slim CI setup

Retrofit **Slim CI** onto an **existing production dbt Orchestra pipeline** (one pipeline for prod and CI). Generate or patch repo artifacts, validate pipeline YAML, and leave a verification checklist. Do not assume warehouse or Git connections can be created via API.

## When to use

- User asks to set up Slim CI, dbt CI/CD in Orchestra, or `run-pipeline` for dbt PR checks.
- Workspace is a dbt repo **or** user supplies dbt repo paths and pipeline YAML location.
- Default scope: **retrofit** an existing production pipeline; do not create a separate CI-only pipeline unless the user opts out of shared `latest_production`.

## Companion skill

After setup, failed PR checks: use **pr-slim-ci-orchestra-debug** (project or org copy). Do not merge debug steps into this skill.

## Workflow

1. **Collect inputs** — Follow [references/inputs-matrix.md](references/inputs-matrix.md). Ask for must-haves; discover from repo when in a dbt project.
2. **Detect context** — In dbt repo: read `dbt_project.yml`, `profiles.yml`, `orchestra/`, `.github/workflows/`. Outside: require repo URL, pipeline YAML path, and where GHA lives. If already configured per Orchestra docs, report and run verification only.
3. **Load Orchestra docs** — Follow [references/orchestra/mcp-playbook.md](../../references/orchestra/mcp-playbook.md) (Orchestra Documentation MCP, then Orchestra MCP).
4. **Inventory pipeline** — `list_pipelines`; read YAML. Checklist: [references/retrofit-checklist.md](references/retrofit-checklist.md).
5. **Patch pipeline YAML** — Minimal changes from [templates/pipeline-inputs-snippet.yml](templates/pipeline-inputs-snippet.yml): `dbt_branch`, `dbt_command` (default = current prod command incl. `--target ${{ ENV.DBT_TARGET }}`), optional `dbt_ci_schema_suffix` passed to the task as `DBT_CI_SCHEMA_SUFFIX`, and `max_active: ${{ ENV.DBT_PIPELINE_CONCURRENCY }}` so CI can run PRs in parallel while prod stays at 1. Git-backed: commit YAML; do not use `update_pipeline`. Orchestra-backed only: `validate_pipeline` then `create_pipeline` / `update_pipeline`.
6. **Orchestra environments** — CI and prod environments (names case-sensitive) with `DBT_TARGET` (`ci` / `prod`) and `DBT_PIPELINE_CONCURRENCY` (e.g. `5` / `1`). Manual unless the environment MCP tools are available and the user approves.
7. **dbt project** — `ci` target alongside `prod` in the Orchestra dbt connection's `profiles.yml` (its `schema` is the per-PR prefix, e.g. `ci` → `ci_123`). Add or merge [templates/dbt/generate_schema_name.sql](templates/dbt/generate_schema_name.sql) and [templates/dbt/drop_ci_schema.sql](templates/dbt/drop_ci_schema.sql) into `macros/`; if the project already overrides `generate_schema_name`, add only the `ci` branch. Projects with incremental models: add [templates/dbt/selectors.yml](templates/dbt/selectors.yml). Bootstrap `latest_production` (successful prod run on default branch).
8. **GitHub Actions** — Add or patch [templates/github-dbt-slim-ci.yml](templates/github-dbt-slim-ci.yml): PR job (CI env, `cancel_on_exit: true`, PR number as `dbt_ci_schema_suffix`), deploy job on merge (prod env, `dbt_branch: main`), and clean-up job dropping `ci_<PR number>` on close. Pin `orchestra-hq/run-pipeline@v1.7.0`+ (`cancel_on_exit` needs it). Incremental models: swap in the `dbt_command` values from [templates/github-dbt-slim-ci-incremental.yml](templates/github-dbt-slim-ci-incremental.yml). Ask how merges should deploy (rebuild modified, full refresh, or leave to the schedule) before keeping the deploy job. Separate pipeline repo: Action `branch` = pipeline YAML branch; `dbt_branch` only in `run_inputs`.
9. **Secrets checklist** — `ORCHESTRA_API_KEY` secret; pipeline id as a secret or `vars.ORCHESTRA_DBT_PIPELINE_ID`. Warehouse creds stay in the Orchestra dbt connection, so GitHub never needs them — including for schema clean-up.
10. **Validate** — `validate_pipeline` when definition available; `dbt parse` when possible. `start_pipeline` with Slim `runInputs` only with user approval.
11. **Report** — Use [references/completion-report.md](references/completion-report.md).

## Guardrails

- One production pipeline for prod + Slim CI unless user wants isolated artifact history.
- Do not implement manual S3 manifest export unless user rejects Orchestra `latest_production`.
- Do not commit API keys or connection secrets.
- Never point CI at the `prod` target or prod schemas; CI writes only to `ci_<PR number>`.
- Do not broaden scope to full pipeline authoring during retrofit.
- Git-backed vs Orchestra-backed determines commits vs MCP create/update.
- Cite Orchestra docs via MCP; treat any single repo as a pattern, not universal defaults.

## Out of scope

Non-GitHub CI (document `start_pipeline` MCP tool / CLI as follow-up), new warehouse/Git OAuth setup, Lightdash preview CI, auto-fixing failing Slim CI runs. CI runs register `ci_<PR number>` tables as Orchestra assets; mention that the user can delete them (assets API / MCP) but do not automate it.

## Doc index

| Topic | URL |
|-------|-----|
| CI/CD for dbt Core | https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd |
| GitHub Actions CI/CD | https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/github_actions |
| dbt Core execute | https://docs.getorchestra.io/docs/integrations/dbt_core/dbt_core_execute |
| Pipeline inputs | https://docs.getorchestra.io/docs/core-concepts/variables/inputs |
| dbt Core in Orchestra | https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup |

Full input matrix and MCP steps: [references/orchestra-slim-ci.md](references/orchestra-slim-ci.md).
