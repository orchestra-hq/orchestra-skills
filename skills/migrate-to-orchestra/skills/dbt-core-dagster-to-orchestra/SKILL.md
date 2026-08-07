---
name: dbt-core-dagster-to-orchestra
description: "Use this skill when the user wants to convert a Dagster dbt integration — DbtCliResource, @dbt_assets, dbt_assets, build_dbt_asset_selection, or DbtProject — into an equivalent Orchestra pipeline task. Triggers: any mention of migrating or rewriting Dagster dbt assets to Orchestra; Dagster code importing from dagster_dbt; @dbt_assets decorated functions running dbt build/run/test/seed/snapshot via DbtCliResource."
---

# dbt Core: Dagster -> Orchestra Conversion

## Overview

In Dagster, dbt Core is a flagship integration via `dagster-dbt`: a `DbtCliResource` runs the dbt CLI and `@dbt_assets` parses the dbt `manifest.json` to produce asset-level lineage. The decorated function streams `dbt.cli([...])` commands.

In Orchestra, dbt Core is a first-class integration. A single **Execute** task under `DBT_CORE` replaces one or more `@dbt_assets`. Orchestra pulls the dbt project from a connected Git repository and runs the commands you specify.

## Parameter Mapping

| Dagster concept | Orchestra YAML field | Notes |
|---|---|---|
| `dbt.cli(["build", "--select", ...])` | `parameters.commands` | Semicolon-separated dbt CLI string |
| Python environment | `parameters.python_version` | e.g. `'3.12'` |
| pip / poetry / uv | `parameters.package_manager` | `PIP`, `POETRY`, or `UV` — infer from visible project files (`poetry.lock`/`pyproject.toml` → `POETRY`, `uv.lock` → `UV`, `requirements.txt`/`Pipfile` → `PIP`). If none of that is visible, don't silently guess `PIP` — see Gotchas |
| `DbtProject(project_dir=...)` (Git repo + project) | `connection:` for the repo/credentials, `parameters.project_dir` for the path | The connection stores the repo URL; `project_dir` is a real task parameter — set it to the same subdirectory value, `null` if the project is at the repo root |
| `--project-dir` | `parameters.project_dir` | Same as above — carry the path over, don't drop it |
| `profiles_dir` / `profiles.yml` | Configured on the connection | Warehouse creds live on the connection |
| `--select` / `--exclude` | Include in `commands` | e.g. `dbt build --select models/marts` |
| `--target` | Include in `commands` or on connection | e.g. `dbt run --target prod` |
| asset key / op name | `name:` | Human-readable task name |

## Orchestra YAML Structure

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        name: <descriptive name>
        connection: <orchestra-dbt-core-connection-name>
        parameters:
          commands: 'dbt seed; dbt build --select tag:daily;'
          package_manager: PIP
          python_version: '3.12'
          project_dir: null   # optional — subdirectory holding dbt_project.yml, e.g. 'dbt' in a monorepo
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

1. **Find the dbt assets** — locate `@dbt_assets` / `DbtCliResource` and read the `dbt.cli([...])` command lists.
2. **Create/verify the Orchestra dbt Core connection** — Settings -> Connections -> dbt Core, pointing at your Git repo (URL, branch, folder) and warehouse credentials. This is also where `package_manager` gets confirmed — see step 3.
3. **Determine `package_manager`** — infer it from visible signals (lockfile/manifest in the repo). If the source gives no such signal, don't silently default to `PIP`: add a `# MANUAL:` comment on the `package_manager` line so it surfaces in the migration checklist for the user to confirm/select when they set up the dbt Core connection.
4. **Carry over `project_dir`** — `DbtProject(project_dir=...)`'s value is a real task parameter, not connection config. Set `parameters.project_dir` to that subdirectory; leave it `null` if the dbt project is at the repo root.
5. **Consolidate commands** — collect the dbt CLI calls into one semicolon-separated `commands` string. Convert each `dbt.cli(["build","--select","x"])` to `dbt build --select x;`.
6. **Replace assets with a single task block** — typically multiple `@dbt_assets` (or seed -> run -> test) collapse into one Orchestra task.
7. **Wire dependencies** — upstream assets (e.g. Fivetran/Airbyte) become `depends_on:`.

## Before / After Example

### Dagster (before)

```python
from pathlib import Path
from dagster import Definitions
from dagster_dbt import DbtCliResource, dbt_assets, DbtProject

dbt_project = DbtProject(project_dir=Path("dbt"))
dbt_resource = DbtCliResource(project_dir=dbt_project)

@dbt_assets(manifest=dbt_project.manifest_path)
def my_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build", "--select", "tag:daily", "--target", "prod"], context=context).stream()

defs = Definitions(assets=[my_dbt_assets], resources={"dbt": dbt_resource})
```

### Orchestra YAML (after)

```yaml
version: v1
name: my-pipeline
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        name: dbt_daily_build
        connection: data_dbt_bigquery_prod_12345
        parameters:
          commands: 'dbt seed; dbt build --select tag:daily --target prod;'
          package_manager: PIP
          python_version: '3.12'
          project_dir: dbt   # from DbtProject(project_dir=Path("dbt")) in the source above
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **`@dbt_assets` granularity** — Dagster expands the manifest into one asset per model/test; Orchestra collapses these into one `DBT_CORE_EXECUTE` task with the same `--select` filter. Observatory still surfaces per-model metadata.
- **`dbt.cli([...])` -> `commands` string** — `["build","--select","tag:daily"]` becomes `dbt build --select tag:daily;`. Join multiple calls with semicolons.
- **profiles.yml** — Orchestra manages warehouse credentials on its dbt Core connection; do not pass `--profiles-dir` or hardcode credentials.
- **`project_dir` is a real task parameter, not connection config** — carry `DbtProject(project_dir=...)`'s value over to `parameters.project_dir` instead of dropping it. Only `null` it if the dbt project genuinely sits at the repo root.
- **Partitioned dbt assets / `--vars`** — Orchestra has no backfill; convert vars to `inputs:` or hardcode and flag partition logic.
- **Manifest** — Dagster needs a compiled `manifest.json`; Orchestra compiles on its runners, so you do not ship the manifest.
- **Can't infer `package_manager`**: don't just guess `PIP` and move on. Flag it instead:
  ```yaml
  package_manager: PIP  # MANUAL: could not detect pip/poetry/uv from the source — confirm/select the correct package manager when setting up the dbt Core connection
  ```
  This surfaces as a Manual Review item in the migration checklist, so the user resolves it alongside connection setup rather than deploying a silently-wrong environment.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/dbt_core
- Orchestra dbt Core setup: https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup
- Dagster dbt: https://docs.dagster.io/integrations/libraries/dbt
- dagster-dbt API: https://docs.dagster.io/api/python-api/libraries/dagster-dbt

## Adding Alerts

If the Dagster code sends notifications via a run failure sensor, `make_slack_on_run_failure_sensor`, or op success/failure hooks, replace those with an `alerts` block in the pipeline YAML. Alerts fire based on overall pipeline status and support Slack, Email, PagerDuty, Microsoft Teams, and Webhook destinations.

```yaml
version: v1
name: my-pipeline

alerts:
  - name: on-failure
    statuses:
      - FAILED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'
    custom_message: 'Optional context message.'

  - name: on-success
    statuses:
      - SUCCEEDED
    destinations:
      - integration: SLACK
        destination: '#data-alerts'

pipeline:
  # ... tasks unchanged
```

Valid statuses: `FAILED`, `SUCCEEDED`, `CANCELLED`, `WARNING`, `SKIPPED`. Multiple alerts with different destinations are supported — each needs a unique `name`. See the `slack-dagster-to-orchestra` skill for full schema details.