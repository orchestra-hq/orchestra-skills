# Orchestra dbt Core task — shared reference

Canonical Orchestra-side syntax for the `DBT_CORE` task, shared by `dbt-core-airflow-to-orchestra`,
`dbt-core-dagster-to-orchestra`, and `dbt-core-prefect-to-orchestra`. Each of those skills covers the
source-specific mapping (which Airflow operator / Dagster resource / Prefect block runs dbt, and how to
recognize a dbt Core invocation in that source); this file is the Orchestra side only — the part that's
identical regardless of source orchestrator.

**Not covered here — stays in each skill, deliberately not shared:** the per-source parameter mapping
tables (BashOperator/SSHOperator/Cosmos vs. `DbtCliResource`/`@dbt_assets` vs.
`DbtCoreOperation`/`ShellOperation`); the "how do I recognize a dbt Core invocation in this source" test,
since the code shapes differ completely per orchestrator; the Before/After conversion examples, since the
"before" half is inherently source-specific; the dbt Cloud (`DBT`/`DBT_RUNJOB`) task shape, which only the
Prefect skill covers; and any sentence naming another orchestrator or a sibling skill.

## DBT_CORE_EXECUTE task shape

```yaml
version: v1
name: <pipeline-name>
pipeline:
  <stage-uuid>:
    tasks:
      <task-uuid>:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        name: <descriptive task name>
        connection: <orchestra-dbt-core-connection-name>
        parameters:
          commands: 'dbt seed; dbt build --select tag:daily;'   # semicolon-separated dbt CLI commands
          package_manager: PIP       # PIP | POETRY | UV
          python_version: '3.12'
          project_dir: null          # optional — subdirectory holding dbt_project.yml, e.g. 'dbt' in a monorepo
        depends_on: []
        condition: null
        tags: []
```

- `connection:` — an Orchestra dbt Core connection, which stores the Git repo URL/branch and warehouse
  credentials. Warehouse credentials and any `--profiles-dir`/`profiles.yml` equivalent belong on this
  connection, never inline in `parameters.commands`.
- `parameters.commands` — every dbt CLI invocation joined into a single semicolon-separated string, in
  execution order (e.g. `dbt seed; dbt build --select tag:daily --target prod;`). `--select`,
  `--exclude`, and `--target` flags stay inline in this string rather than becoming separate parameters.
- `parameters.project_dir` — a real task parameter, not connection config. Set it to the subdirectory
  holding `dbt_project.yml` (e.g. `dbt` in a monorepo); leave it `null` if the dbt project sits at the
  repo root. Whatever mechanism the source uses to point at that subdirectory, carry the path over here
  rather than dropping it.

## Determining the package manager

Infer `parameters.package_manager` (`PIP`, `POETRY`, or `UV`) from visible signals in the repo:
`poetry.lock`/`pyproject.toml` -> `POETRY`, `uv.lock` -> `UV`, `requirements.txt`/`Pipfile` -> `PIP`.

If none of that is visible, don't silently default to `PIP`. Flag it instead:

```yaml
package_manager: PIP  # MANUAL: could not detect pip/poetry/uv from the source — confirm/select the correct package manager when setting up the dbt Core connection
```

This surfaces as a Manual Review item in the migration checklist, so the user resolves it alongside
connection setup rather than deploying a silently-wrong environment.

## References

- Orchestra dbt Core integration docs: https://docs.getorchestra.io/docs/integrations/dbt_core
- Orchestra dbt Core setup guide: https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup
