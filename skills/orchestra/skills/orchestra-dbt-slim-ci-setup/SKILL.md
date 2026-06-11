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
5. **Patch pipeline YAML** — Minimal changes from [templates/pipeline-inputs-snippet.yml](templates/pipeline-inputs-snippet.yml). Git-backed: commit YAML; do not use `update_pipeline`. Orchestra-backed only: `validate_pipeline` then `create_pipeline` / `update_pipeline`.
6. **GitHub Actions** — Add or patch workflow from [templates/github-dbt-slim-ci.yml](templates/github-dbt-slim-ci.yml). Separate pipeline repo: Action `branch` = pipeline YAML branch; `dbt_branch` only in `run_inputs`.
7. **dbt prerequisites** — CI/prod targets in Orchestra connection profiles; excludes in Slim command; bootstrap `latest_production` (successful prod run on default branch).
8. **Secrets checklist** — Document `ORCHESTRA_API_KEY`, optional pipeline/task id secrets, GHA environment → Orchestra environment mapping. Warehouse creds stay in Orchestra dbt connection.
9. **Validate** — `validate_pipeline` when definition available; `dbt parse` when possible. `start_pipeline` with Slim `runInputs` only with user approval.
10. **Report** — Use [references/completion-report.md](references/completion-report.md).

## Guardrails

- One production pipeline for prod + Slim CI unless user wants isolated artifact history.
- Do not implement manual S3 manifest export unless user rejects Orchestra `latest_production`.
- Do not commit API keys or connection secrets.
- Do not broaden scope to full pipeline authoring during retrofit.
- Git-backed vs Orchestra-backed determines commits vs MCP create/update.
- Cite Orchestra docs via MCP; treat any single repo as a pattern, not universal defaults.

## Out of scope

Non-GitHub CI (document `start_pipeline` MCP tool / CLI as follow-up), new warehouse/Git OAuth setup, Lightdash preview CI, auto-fixing failing Slim CI runs.

## Doc index

| Topic | URL |
|-------|-----|
| CI/CD for dbt Core | https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd |
| GitHub Actions CI/CD | https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/github_actions |
| dbt Core execute | https://docs.getorchestra.io/docs/integrations/dbt_core/dbt_core_execute |
| Pipeline inputs | https://docs.getorchestra.io/docs/core-concepts/variables/inputs |
| dbt Core in Orchestra | https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup |

Full input matrix and MCP steps: [references/orchestra-slim-ci.md](references/orchestra-slim-ci.md).
