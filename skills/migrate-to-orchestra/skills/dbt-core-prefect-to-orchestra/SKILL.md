---
name: dbt-core-prefect-to-orchestra
description: "Use this skill when the user wants to convert a Prefect task that runs dbt Core commands — DbtCoreOperation block, ShellOperation running dbt CLI, run_dbt_build / run_dbt_test tasks, or DbtCloudJob — into an equivalent Orchestra pipeline task. Triggers: any mention of migrating or rewriting Prefect dbt tasks to Orchestra; any Prefect flow code importing from prefect_dbt; ShellOperation commands starting with 'dbt '."
---

## Overview

Converts Prefect dbt tasks into Orchestra pipeline YAML. Two dbt variants exist:

- **dbt Core** (`DbtCoreOperation`, `ShellOperation` running `dbt` CLI): `integration: DBT_CORE`, `integration_job: DBT_CORE_EXECUTE`
- **dbt Cloud** (`DbtCloudJob`): `integration: DBT`, `integration_job: DBT_RUNJOB`

The `commands` list from Prefect is joined into a single semicolon-delimited string. Warehouse credentials and Git repo details go on the Orchestra dbt Core connection, not in YAML.

## Parameter Mapping

| Prefect construct | Orchestra field | Notes |
|---|---|---|
| `DbtCoreOperation(commands=[...])` | `parameters.commands` | Join list items with `; ` — e.g. `'dbt seed; dbt build;'` |
| Python version | `parameters.python_version` | `'3.11'` or `'3.12'` |
| pip / poetry / uv | `parameters.package_manager` | `PIP`, `POETRY`, or `UV` — infer from visible project files (`poetry.lock`/`pyproject.toml` → `POETRY`, `uv.lock` → `UV`, `requirements.txt`/`Pipfile` → `PIP`). If none of that is visible, don't silently guess `PIP` — see Gotchas |
| Git repo + profiles.yml / warehouse creds | `connection:` | Set up in Connectors → dbt Core |
| `--select`, `--exclude`, `--target` flags | inline in `parameters.commands` | e.g. `dbt build --select tag:daily --target prod;` |
| `project_dir` | `parameters.project_dir` | A real task parameter — the subdirectory holding `dbt_project.yml`. Carry the value over; `null` if the project is at the repo root |
| `DbtCloudJob(job_id=..., account_id=...)` | `integration: DBT`, `integration_job: DBT_RUNJOB`, `parameters.job_id` | account_id goes on the Orchestra dbt Cloud connection |
| `ShellOperation(commands=["dbt build"])` | same as `DbtCoreOperation` | Treat identically |

## Orchestra YAML Structure

**dbt Core:**

```yaml
version: v1
name: dbt-flow
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
          project_dir: null   # optional — subdirectory holding dbt_project.yml, e.g. 'dbt' in a monorepo
        depends_on: []
        condition: null
        tags: []
```

**dbt Cloud:**

```yaml
version: v1
name: dbt-cloud-flow
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: DBT
        integration_job: DBT_RUNJOB
        name: dbt_cloud_job
        connection: dbt_cloud_prod_12345
        parameters:
          job_id: '123456'
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

- [ ] Determine dbt variant: `DbtCoreOperation` / `ShellOperation` → DBT_CORE; `DbtCloudJob` → DBT
- [ ] **dbt Core:** join `commands` list with `'; '` and append trailing `;` into `parameters.commands`
- [ ] **dbt Core:** choose `parameters.package_manager` (PIP/POETRY/UV) to match project setup — if it can't be inferred, add a `# MANUAL:` comment flagging it for the user to confirm/select when they set up the dbt Core connection, rather than silently defaulting to PIP
- [ ] **dbt Core:** choose `parameters.python_version` (`'3.11'` or `'3.12'`)
- [ ] **dbt Core:** carry `project_dir` over to `parameters.project_dir` (a real task parameter — don't drop it); move `profiles.yml` and warehouse credentials to the Orchestra dbt Core connection
- [ ] **dbt Cloud:** set `parameters.job_id` to the numeric job ID string; set `account_id` on the connection
- [ ] Set `connection:` to the appropriate Orchestra connection name
- [ ] Wire `depends_on:` if this task follows a Fivetran sync or other upstream task
- [ ] Add an `alerts:` block if the Prefect flow had on_failure/on_completion hooks

## Before / After Example

### Prefect (before)

```python
from prefect import flow
from prefect_dbt.cli import DbtCoreOperation

@flow
def dbt_flow():
    with DbtCoreOperation(
        commands=["dbt seed", "dbt build --select tag:daily --target prod"],
        project_dir="dbt_project",
    ) as dbt_op:
        dbt_op.run()
```

### Orchestra YAML (after)

```yaml
version: v1
name: dbt-flow
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
          project_dir: dbt_project   # from DbtCoreOperation(project_dir="dbt_project") in the source above
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- `DbtCoreOperation.commands` is a Python list — **join with semicolons** for Orchestra (`'dbt seed; dbt build;'`); a missing trailing `;` can cause parse errors
- `project_dir` is a real task parameter — carry `DbtCoreOperation(project_dir=...)`'s value over to `parameters.project_dir` instead of dropping it. Only `null` it if the dbt project genuinely sits at the repo root.
- `profiles.yml` and warehouse credentials go on the Orchestra dbt Core connection, **never** in YAML
- `DbtCloudJob` (Cloud) uses a different integration pair: `integration: DBT`, `integration_job: DBT_RUNJOB`, `parameters: {job_id: "123456"}`
- `ShellOperation(commands=["dbt build"])` is treated identically to `DbtCoreOperation`
- `--select`, `--exclude`, and `--target` flags belong inside the `commands` string, not as separate parameters
- **Can't infer `package_manager`**: don't just guess `PIP` and move on. Flag it instead:
  ```yaml
  package_manager: PIP  # MANUAL: could not detect pip/poetry/uv from the source — confirm/select the correct package manager when setting up the dbt Core connection
  ```
  This surfaces as a Manual Review item in the migration checklist, so the user resolves it alongside connection setup rather than deploying a silently-wrong environment.

## References

- https://docs.getorchestra.io/docs/integrations/dbt_core
- https://docs.getorchestra.io/docs/integrations/dbt
- https://prefecthq.github.io/prefect-dbt/

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
