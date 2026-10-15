# Pipeline retrofit checklist

Inventory the **existing production** dbt pipeline before editing. Prefer **one pipeline and one dbt Core task** for scheduled prod and Slim CI: artifact history is scoped to each dbt Core task, so only that task's own successful default-branch runs seed its `latest_production`.

## Orchestra MCP inventory

1. `list_pipelines` — match user pipeline id or alias.
2. Load definition from Git-backed YAML in workspace or user path; Orchestra-backed via the `get_pipeline` MCP tool.
3. Identify the **primary** `DBT_CORE` / `DBT_CORE_EXECUTE` task used in production (note task key, e.g. `run_dbt`).

## Checklist

| Check | Expected |
|-------|----------|
| `inputs.dbt_branch` | `type: string`, default = default branch (e.g. `main`) |
| `inputs.dbt_command` | `type: string`, default = current prod command (without leading `dbt`), incl. `--target ${{ ENV.DBT_TARGET }}` |
| `inputs.dbt_ci_schema_suffix` | `type: string`, `optional: true` — CI passes the PR number |
| Task `parameters.branch` | `${{ inputs.dbt_branch }}` on prod dbt task (and snapshot tasks if they must follow same branch) |
| Task `parameters.commands` | `dbt ${{ inputs.dbt_command }}` — keep `--target` inside the input, not appended here, or only the last of several `;`-chained commands gets it |
| Task `parameters.environment_variables` | `'{"DBT_CI_SCHEMA_SUFFIX": "${{ inputs.dbt_ci_schema_suffix }}"}'` — a JSON string; a YAML mapping fails validation |
| `configuration.concurrency.max_active` | `${{ ENV.DBT_PIPELINE_CONCURRENCY }}` (see Concurrency below) |
| `production_run_identifier` | Set only if baseline ≠ dbt repo default branch (branch name or commit SHA; **git tags are not supported**). An identifier that does not resolve leaves `latest_production` empty for that run |
| Dedicated CI-only pipeline **or a second dbt Core task for CI** | **Avoid** — artifact history is per task, so a new task's `latest_production` is empty (or missing) until that task itself succeeds on the default branch |

## Minimal YAML patch

**Pipeline inputs** (preserve prod default selector from current scheduled run):

```yaml
inputs:
  dbt_branch:
    type: string
    default: main
  dbt_command:
    type: string
    default: build --select <prod_selector> --target ${{ ENV.DBT_TARGET }}
  dbt_ci_schema_suffix:
    type: string
    optional: true
```

**Production dbt task** (task key varies):

```yaml
parameters:
  commands: dbt ${{ inputs.dbt_command }}
  branch: ${{ inputs.dbt_branch }}
  environment_variables: '{"DBT_CI_SCHEMA_SUFFIX": "${{ inputs.dbt_ci_schema_suffix }}"}'
  # production_run_identifier: main
```

Apply only missing pieces. Do not rename unrelated tasks or restructure groups.

## Storage provider

| Type | Agent action |
|------|----------------|
| Git-backed | Edit YAML in repo; commit; **do not** `update_pipeline` via MCP |
| Orchestra-backed | `validate_pipeline` on JSON definition, then `create_pipeline` / `update_pipeline` |

## `latest_production`

Orchestra injects artifacts before each dbt task run from **that same task's** last **successful** run on the dbt repo **default branch** (unless `production_run_identifier` overrides). History is per dbt Core task, not per pipeline — CI deferring to production state only works when CI runs the production task itself. Empty state: run a successful non-defer prod build of that task on the default branch once before Slim CI. See [dbt artifacts - `latest_production`](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd#dbt-artifacts-latest_production) and [completion-report.md](completion-report.md).

## `dbt clone` and `--defer`

Cloning the **whole** dbt target into `ci_<PR number>` leaves the later `dbt build` commands able to read unmodified upstream models from the clones, so `--defer` is not needed on them. `--defer` is only required after a clone when the clone covered a **subset** of the target (e.g. a selector was passed to `dbt clone`) — then the uncloned upstreams still have to resolve to production. Keep `--state latest_production` regardless: `state:modified+` and the `modified_incremental` selector compare against it whether or not anything defers. A deploy job that doesn't clone at all still needs `--defer`. See [Set up dbt Slim CI and CD with Orchestra](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd#set-up-dbt-slim-ci-and-cd-with-orchestra).

## Separate pipeline repo

- GHA `branch` on `orchestra-hq/run-pipeline` = branch of **pipeline YAML** repo (usually `main`).
- `run_inputs.dbt_branch` = PR branch for **dbt** checkout on the task.
- `latest_production` resolves from the dbt task's own history and branch settings, not the pipeline YAML branch.

## Concurrency (shared prod + CI pipeline)

- A fixed `configuration.concurrency.max_active` applies in every environment, so a prod limit of `1` also serialises PR runs. What a blocked run does depends on `configuration.concurrency.on_limit`: the default `SKIP` creates it as `SKIPPED`, and `run-pipeline` only logs a warning rather than failing the check — check its `status` output if a skipped PR run should block the PR. `QUEUE` instead holds the run as `QUEUED` until a slot frees, so the GHA job waits rather than reporting early; that turns a concurrency problem into a slow check, and a run still waiting after 24 hours expires as `SKIPPED` anyway. Don't reach for `QUEUE_LATEST` on a CI pipeline — a newer PR run would skip an older PR's still-waiting run, reporting a false result on the wrong PR. Prefer separate per-environment limits below over queueing CI behind prod.
- To give CI and prod separate limits, set `max_active: ${{ ENV.DBT_PIPELINE_CONCURRENCY }}` and define the variable per Orchestra environment (e.g. `CI` = 5, `Production` = 1). See [dbt CI/CD](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd) and [run-pipeline outputs](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/github_actions).
