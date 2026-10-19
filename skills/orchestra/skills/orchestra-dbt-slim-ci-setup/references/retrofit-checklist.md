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
| `configuration.concurrency.on_limit` | `${{ ENV.DBT_PIPELINE_ON_LIMIT }}` (see Concurrency below) |
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

## Giving CI a production-like starting point

Two supported strategies. Pick one with the user before writing `dbt_command`; they differ in what
lands in `ci_<PR number>`, not just in speed.

| | `dbt clone` | `--defer` only |
|---|---|---|
| Pick it when | Incremental merge logic has to be tested against real existing production data; the CI build role must be kept out of production; or `ci_<PR number>` has to hold the whole project (to query it, or point BI at it) | Runs should be fast and the change is simple model logic on a subset of the project; the `ci` target can read production directly |
| `ci_<PR number>` holds | Every production relation, plus the modified models | Only modified models and everything downstream — nothing is created for unmodified models |
| Unmodified upstreams read from | Clones in `ci_<PR number>` | Production schemas, always current |
| Unmodified incrementals downstream of a change | Run incrementally on the cloned data | Built from scratch — slow on large tables |
| Freshness | Point-in-time copy, goes stale as production moves | Always the latest production tables |
| `ci` target needs | Read production, create clones or views in the CI schema | Read production, create tables in the CI schema |

Commands for each (the task prefixes `dbt`, so chained commands after `;` start with `dbt`):

```bash
# dbt clone
dbt clone --state latest_production --target ci
dbt build --full-refresh --selector modified_incremental --defer --state latest_production --target ci
dbt build -s state:modified+ --defer --state latest_production --target ci

# --defer only (same two builds the deploy-on-merge job runs; only the target differs)
dbt build --full-refresh --selector modified_incremental --defer --state latest_production --target ci
dbt build -s state:modified+ --defer --state latest_production --target ci
```

Under `--defer` only, nothing is cloned, so the first `build` is what creates the modified
incremental models in `ci_<PR number>` and gives the second an existing table to run incrementally
against — `is_incremental()` is exercised, but against a table just built from scratch rather than
against existing production data. That is the real test-fidelity cost of skipping the clone.

### `--favor-state`

`--defer` prefers a relation that **already exists in `ci_<PR number>`** over the production one. If
an earlier commit on the PR built a model and a later commit reverts it, CI silently reads the stale
copy. Add `--favor-state` to the build commands to always resolve unselected models to production.
Recommend it on any long-lived PR schema; it matters most in the `--defer`-only strategy, where the
CI schema accumulates only what previous commits happened to build.

### `--defer` after a clone

Cloning the **whole** target leaves the later builds able to read unmodified upstreams from the
clones, so `--defer` is not required for them. It becomes required again when the clone covered a
**subset** of the target (e.g. a selector was passed to `dbt clone`), for whatever the clone left
out. Keep `--state latest_production` either way: `state:modified+` and the `modified_incremental`
selector compare against it whether or not anything defers. A deploy job that never clones always
needs `--defer`.

### Keeping the CI build role out of production

With `dbt clone`, run the clone under a **separate target** whose role can read production; the CI
build then reads only the clones and needs no production access. This depends on zero-copy clones —
on warehouses without them `dbt clone` creates views that still read production, so the isolation is
lost. `--defer` only cannot offer this: it reads production by design.

See [Set up dbt Slim CI and CD with Orchestra](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd#set-up-dbt-slim-ci-and-cd-with-orchestra).

## Development workflows with `--defer`

Because `--defer` only reads production, a developer can build just their own changes against
production data without copying anything, reusing the same parametrised pipeline:

- **In Orchestra:** run the pipeline manually in the `CI` environment with `dbt_branch` = feature
  branch, `dbt_ci_schema_suffix` = a personal suffix such as `dev_<name>`, and `dbt_command` =
  `build -s state:modified+ --defer --state latest_production --target ci`. The `drop_ci_schema`
  macro cleans up afterwards.
- **Locally:** download the production `manifest.json` from a task run into e.g. `prod_state/`, then
  `dbt build -s state:modified+ --defer --state prod_state` against a personal dev target.

Offer this when the user asks about developer workflows; do not add it to the CI workflow file.

See [Use `--defer` for development workflows](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd#use-defer-for-development-workflows).

## Separate pipeline repo

- GHA `branch` on `orchestra-hq/run-pipeline` = branch of **pipeline YAML** repo (usually `main`).
- `run_inputs.dbt_branch` = PR branch for **dbt** checkout on the task.
- `latest_production` resolves from the dbt task's own history and branch settings, not the pipeline YAML branch.

## Concurrency (shared prod + CI pipeline)

- A fixed `configuration.concurrency.max_active` applies in every environment, so a prod limit of `1` also serialises PR runs. What a blocked run does depends on `configuration.concurrency.on_limit`: the default `SKIP` creates it as `SKIPPED`, and `run-pipeline` only logs a warning rather than failing the check — check its `status` output if a skipped PR run should block the PR. `QUEUE` instead holds the run as `QUEUED` until a slot frees, so the GHA job waits rather than reporting early; that turns a concurrency problem into a slow check, and a run still waiting after 24 hours expires as `SKIPPED` anyway.
- Scope **both** settings per environment rather than queueing CI behind prod: `max_active: ${{ ENV.DBT_PIPELINE_CONCURRENCY }}` and `on_limit: ${{ ENV.DBT_PIPELINE_ON_LIMIT }}`, each defined per Orchestra environment. The documented starting point is `CI` = `5` / `QUEUE_LATEST` and `Production` = `1` / `QUEUE`: CI runs several PRs at once and, at the limit, keeps only the newest waiting run instead of queueing one per commit, while a merge-triggered prod deploy waits for an in-progress scheduled run rather than being skipped. See [dbt CI/CD](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd) and [run-pipeline outputs](https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/github_actions).
- Raise the `QUEUE_LATEST` trade-off with the user before setting it in CI. The queue is scoped per pipeline and environment (plus branch for Git-backed pipelines), and `run-pipeline`'s `branch` is the **pipeline YAML** repo's branch, so every PR shares one CI queue. Once CI is at `max_active`, a run from a newer PR skips an older PR's still-waiting run and `run-pipeline` only warns. Set `max_active` high enough that PRs rarely queue, and check `status` if a skipped PR run should block the PR. Use `QUEUE` in CI instead when every PR run must report a real result.
