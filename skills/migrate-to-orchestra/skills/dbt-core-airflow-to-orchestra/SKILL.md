---
name: dbt-core-airflow-to-orchestra
description: "Use this skill when the user wants to convert an Airflow task that runs dbt Core commands — via BashOperator, SSHOperator, PythonOperator, KubernetesPodOperator, or Astronomer Cosmos — into an equivalent Orchestra pipeline task. Triggers: any mention of migrating or rewriting dbt Core Airflow tasks to Orchestra; Airflow DAG code running dbt CLI commands (dbt run, dbt test, dbt build, dbt seed, dbt snapshot) regardless of which operator invokes them, including SSHOperator tasks that SSH into a remote server to run dbt; Cosmos DbtTaskGroup or DbtRunOperator."
---

# dbt Core: Airflow → Orchestra Conversion

## Overview

In Airflow, dbt Core is typically run via:
- `BashOperator` executing `dbt run` / `dbt build` / etc.
- `SSHOperator` SSH-ing into a remote server that runs `dbt run` / `dbt build` / etc.
- `KubernetesPodOperator` running a dbt Docker image
- Astronomer Cosmos (`DbtTaskGroup`, `DbtRunOperator`, etc.)

In Orchestra, dbt Core is a first-class integration. A single **Execute** task under `DBT_CORE` replaces one or more Airflow tasks. Orchestra pulls the dbt project from a connected Git repository and runs the commands you specify.

**This applies no matter which operator wrapped the dbt call in Airflow.** If the task body is a dbt CLI command (`dbt run`, `dbt build`, `dbt test`, `dbt seed`, `dbt snapshot`), convert it to `DBT_CORE_EXECUTE` — even if it arrived via `SSHOperator` against a remote dbt server. Don't fall back to a literal `LINUX_SSH` translation (see `airflow-bash-ssh-to-orchestra`) just because the source operator happens to be SSH-based; the SSH-server detail is an Airflow deployment artifact, not something to preserve. Point the converted task at an Orchestra dbt Core connection (Git repo + warehouse credentials) instead of the SSH connection.

## Parameter Mapping

### BashOperator with dbt CLI

| Airflow / shell concept | Orchestra YAML field | Notes |
|---|---|---|
| `bash_command` (the dbt command string) | `parameters.commands` | Semicolon-separated list of dbt CLI commands |
| Python version in environment | `parameters.python_version` | e.g. `'3.12'` |
| pip / poetry / uv | `parameters.package_manager` | `PIP`, `POETRY`, or `UV` — infer from visible project files (`poetry.lock`/`pyproject.toml` → `POETRY`, `uv.lock` → `UV`, `requirements.txt`/`Pipfile` → `PIP`) or explicit invocations (`poetry run dbt ...`, `uv run dbt ...`). If none of that is visible, don't silently guess `PIP` — see Gotchas |
| Git repo + branch (where dbt project lives) | `connection:` | Orchestra dbt Core connection (stores Git repo URL + credentials) |
| `--project-dir` | `parameters.project_dir` | Subdirectory within the repo where `dbt_project.yml` lives — a real task parameter, not connection config. Leave `null` if the project is at the repo root; set it for monorepos (e.g. `dbt/` or `analytics/dbt_project`) |
| `--profiles-dir` / `profiles.yml` | Configured on Orchestra connection | Set the warehouse connection on the dbt Core connection in Orchestra |
| `--select` / `--exclude` | Include in `parameters.commands` | e.g. `dbt build --select models/marts` |
| `--target` | Include in command or set on connection | e.g. `dbt run --target prod` |
| `task_id` | `name:` | Human-readable task name |

### SSHOperator with dbt CLI

| Airflow / shell concept | Orchestra YAML field | Notes |
|---|---|---|
| `command` (the dbt command string) | `parameters.commands` | Same treatment as `bash_command` above — strip `cd <dir> &&` and `--profiles-dir`; carry `--project-dir`'s value over to `parameters.project_dir` instead of dropping it |
| `ssh_conn_id` (remote dbt server) | *(dropped)* | Not needed — Orchestra's dbt Core connection replaces the remote server entirely |
| Git repo + branch (where dbt project lives on the remote server) | `connection:` | Orchestra dbt Core connection; if the remote server's dbt project isn't in Git yet, that's a prerequisite to migrating this task |
| `task_id` | `name:` | Human-readable task name |

### Astronomer Cosmos

| Cosmos concept | Orchestra equivalent | Notes |
|---|---|---|
| `DbtTaskGroup` (whole project) | Single `DBT_CORE_EXECUTE` task | Orchestra runs the full sequence as one task |
| `DbtRunOperator` | `DBT_CORE_EXECUTE` with `dbt run` | |
| `DbtTestOperator` | `DBT_CORE_EXECUTE` with `dbt test` | |
| `DbtSeedOperator` | `DBT_CORE_EXECUTE` with `dbt seed` | |
| `select=` / `exclude=` | `--select` / `--exclude` in commands | |
| `profile_config` | Orchestra dbt Core connection | |

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
        name: <task_id or descriptive name>
        connection: <orchestra-dbt-core-connection-name>
        parameters:
          commands: 'dbt seed; dbt build --select models tag:daily;'
          package_manager: PIP       # or POETRY or UV
          python_version: '3.12'
          project_dir: null          # optional — subdirectory holding dbt_project.yml, e.g. 'dbt' in a monorepo
        depends_on: []
        condition: null
        tags: []
```

## Conversion Steps

1. **Identify the Airflow tasks** — find all `BashOperator` or `SSHOperator` tasks running `dbt` commands. If using Cosmos, find the `DbtTaskGroup`.
2. **Create/verify the Orchestra dbt Core connection** — in Orchestra Settings → Connections, create a *dbt Core* connection pointing to your Git repository (URL, branch, folder path) and your data warehouse credentials (via `profiles.yml` equivalent). This is also where `package_manager` gets confirmed — see step 3.
3. **Determine `package_manager`** — infer it from visible signals (lockfile/manifest in the repo, or an explicit `poetry run`/`uv run` invocation). If the source gives no such signal, don't silently default to `PIP`: add a `# MANUAL:` comment on the `package_manager` line so it surfaces in the migration checklist for the user to confirm/select when they set up the dbt Core connection.
4. **Carry over `--project-dir`** — if the source passes `--project-dir <path>` or `cd`s into a subdirectory before running dbt, set `parameters.project_dir` to that path. Leave it `null` if the dbt project is at the repo root.
5. **Consolidate commands** — collect the ordered dbt commands into a single semicolon-separated string for `parameters.commands`.
6. **Replace task(s) with a single block** — typically multiple Airflow tasks (seed → run → test) become one Orchestra task with chained commands.
7. **Wire dependencies** — any Airflow tasks that feed into the dbt block map to `depends_on:`.

## Before / After Example

### Airflow DAG (before)

```python
from airflow.operators.bash import BashOperator

dbt_seed = BashOperator(
    task_id="dbt_seed",
    bash_command="cd /opt/airflow/repo/dbt_project && dbt seed --profiles-dir /opt/airflow/repo/dbt_project",
)

dbt_run = BashOperator(
    task_id="dbt_run_daily",
    bash_command="cd /opt/airflow/repo/dbt_project && dbt build --select tag:daily --profiles-dir /opt/airflow/repo/dbt_project --target prod",
)

dbt_seed >> dbt_run
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
          project_dir: dbt_project   # the repo's clone root is /opt/airflow/repo — this is the subdirectory dbt_project.yml lives in
        depends_on: []
        condition: null
        tags: []
```

## Gotchas

- **SSHOperator running dbt is still a dbt task, not an SSH task**: convert to `DBT_CORE_EXECUTE`, not `LINUX_SSH`. The remote server in `ssh_conn_id` was Airflow's way of reaching the dbt project; Orchestra reaches it via a Git-backed dbt Core connection instead, so the SSH connection itself is dropped from the conversion. If the dbt project on that remote server isn't tracked in Git, flag that as a prerequisite rather than silently emitting a `LINUX_SSH` task.
- **profiles.yml**: Orchestra manages warehouse credentials via its dbt Core connection — do not hardcode credentials in the command string.
- **Cosmos `DbtTaskGroup` granularity**: Cosmos creates one Airflow task per dbt model/test. Orchestra collapses these back to one task with a select filter. This is intentional — Observatory still provides per-model metadata.
- **`--project-dir` is a real task parameter, not connection config**: set `parameters.project_dir` to the subdirectory holding `dbt_project.yml` (e.g. `dbt_project` in a monorepo); leave it `null` if the project is at the repo root. Don't just drop `--project-dir`/`cd <dir> &&` — carry the path over instead of silently discarding it.
- **Slim CI / state**: if the Airflow DAG uses `dbt build --state` for deferred runs, configure this in Orchestra's dbt Core connection settings (artifact storage).
- **KubernetesPodOperator**: if dbt runs in a pod, you're likely managing the Docker image. In Orchestra dbt Core, the environment is managed; migrate the `requirements.txt` or `packages.yml` instead.
- **Can't infer `package_manager`**: don't just guess `PIP` and move on. Flag it instead:
  ```yaml
  package_manager: PIP  # MANUAL: could not detect pip/poetry/uv from the source — confirm/select the correct package manager when setting up the dbt Core connection
  ```
  This surfaces as a Manual Review item in the migration checklist, so the user resolves it alongside connection setup rather than deploying a silently-wrong environment.

## References

- Orchestra docs: https://docs.getorchestra.io/docs/integrations/dbt_core
- Orchestra dbt Core setup guide: https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup
- Live example YAML: https://docs.getorchestra.io/docs/git-control-and-ci-cd/git-control

## Adding Alerts

If the Airflow DAG uses `on_failure_callback` or `on_success_callback` for Slack/email notifications, replace those with an `alerts` block in the pipeline YAML. Alerts fire based on overall pipeline status and support Slack, Email, PagerDuty, Microsoft Teams, and Webhook destinations.

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

Valid statuses: `FAILED`, `SUCCEEDED`, `CANCELLED`, `WARNING`, `SKIPPED`. Multiple alerts with different destinations are supported — each needs a unique `name`. See the `slack-airflow-to-orchestra` skill for full schema details.
