# Pipeline retrofit checklist

Inventory the **existing production** dbt pipeline before editing. Prefer **one pipeline** for scheduled prod and Slim CI so `latest_production` shares lineage.

## Orchestra MCP inventory

1. `list_pipelines` — match user pipeline id or alias.
2. Load definition from Git-backed YAML in workspace or user path; Orchestra-backed from API/UI export.
3. Identify the **primary** `DBT_CORE` / `DBT_CORE_EXECUTE` task used in production (note task key, e.g. `run_dbt`).

## Checklist

| Check | Expected |
|-------|----------|
| `inputs.dbt_branch` | `type: string`, default = default branch (e.g. `main`) |
| `inputs.dbt_command` | `type: string`, default = current prod command (without leading `dbt`) |
| Task `parameters.branch` | `${{ inputs.dbt_branch }}` on prod dbt task (and snapshot tasks if they must follow same branch) |
| Task `parameters.commands` | `dbt ${{ inputs.dbt_command }}` plus existing suffixes (e.g. `--target ${{ ENV.DBT_TARGET }}`) |
| `production_run_identifier` | Set only if baseline ≠ dbt repo default branch (branch name or commit SHA; not tags) |
| Dedicated CI-only pipeline | **Avoid** unless user accepts separate `latest_production` history |

## Minimal YAML patch

**Pipeline inputs** (preserve prod default selector from current scheduled run):

```yaml
inputs:
  dbt_branch:
    type: string
    default: main
  dbt_command:
    type: string
    default: build --select <prod_selector>
```

**Production dbt task** (task key varies):

```yaml
parameters:
  commands: dbt ${{ inputs.dbt_command }} --target ${{ ENV.DBT_TARGET }}
  branch: ${{ inputs.dbt_branch }}
  # production_run_identifier: main
```

Apply only missing pieces. Do not rename unrelated tasks or restructure groups.

## Storage provider

| Type | Agent action |
|------|----------------|
| Git-backed | Edit YAML in repo; commit; **do not** `update_pipeline` via MCP |
| Orchestra-backed | `validate_pipeline` on JSON definition, then `create_pipeline` / `update_pipeline` |

## `latest_production`

Orchestra injects artifacts before each dbt task run from the last **successful** run on the dbt repo **default branch** (unless `production_run_identifier` overrides). Empty state: run a successful non-defer prod build on default branch once before Slim CI. See [completion-report.md](completion-report.md).

## Separate pipeline repo

- GHA `branch` on `orchestra-hq/run-pipeline` = branch of **pipeline YAML** repo (usually `main`).
- `run_inputs.dbt_branch` = PR branch for **dbt** checkout on the task.
- `latest_production` resolves from dbt task branch settings, not pipeline YAML branch.
