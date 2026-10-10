# Audit existing Slim CI setup

Run before patching anything. Accounts often hold earlier, partial attempts: a CI-only pipeline, a
manual manifest export, a second dbt task. Patching the named pipeline without finding these leaves
two setups fighting over the same PRs. Output is a gap table and a fix plan the user approves.

## 1. Sweep the account

| Source | Read |
|--------|------|
| `list_pipelines` | Every pipeline with a `DBT_CORE` task, or a name containing `ci`, `slim`, `pr`, `preprod`, `staging`, `dbt` |
| `get_pipeline` (each candidate) | Inputs, dbt task `commands` / `branch` / `environment_variables` / `production_run_identifier`, `configuration.concurrency`, conditions, Python tasks |
| `list_pipeline_runs` (each candidate, recent) | Which runs succeed, which branch and environment, last success on the default branch |
| `list_environments` | Environment names and whether `DBT_TARGET` / `DBT_PIPELINE_CONCURRENCY` exist |
| dbt repo (if available) | `.github/workflows/*` calling `run-pipeline` or running dbt directly, `macros/generate_schema_name.sql`, `drop_ci_schema`, `selectors.yml`, `profiles.yml` targets |

Git-backed pipelines: read the repo YAML, not only the stored definition.

## 2. Signals of earlier attempts

| Signal | Why it matters |
|--------|----------------|
| Separate CI-only dbt pipeline or second dbt task for CI | Own artifact history: `latest_production` is empty or stale, so `state:modified` selects everything or nothing |
| Python task exporting `manifest.json` (S3/GCS), `run_type == 'CI'` conditions, `PreProd` environment | Manual pattern superseded by `latest_production`; extra moving parts to retire |
| GHA job running `dbt` directly with warehouse secrets | Bypasses Orchestra; credentials duplicated in GitHub |
| `--target` appended to task `commands` | Only the last `;`-chained command gets it |
| Fixed `max_active` on a shared prod + CI pipeline | PR runs `SKIPPED` while prod runs, and the check still passes |
| `run-pipeline` below v1.7.0 or no `cancel_on_exit` | Superseded PR runs keep building into the same schema |
| CI on the `prod` target or prod schemas | PR code writes to production data |
| No per-PR schema / no clean-up | PRs collide in one CI schema; schemas pile up |
| CI pipeline with no successful run in 30+ days | Abandoned attempt still triggered by GHA, or dead weight |

## 3. Gap table

One row per component of the docs pattern. Real state only; fold evidence into the row.

| Status | Meaning |
|--------|---------|
| ✅ | Present and matches the docs |
| ⚠️ | Present but partial or misconfigured |
| ❌ | Missing |
| 🔀 | Conflicting: more than one implementation |

Components: one prod pipeline + one dbt task for CI · parametrised `dbt_command` / `dbt_branch` ·
`latest_production` populated · `ci` target in connection · per-PR schema · per-env concurrency ·
PR workflow (CI env, `cancel_on_exit`) · deploy on merge · schema clean-up · incremental variant
(only if the project has incremental models).

## 4. Fix plan

Numbered, in dependency order. Tag each step:

- **[agent, approval]** — the agent does it after an explicit yes (commit YAML, `update_pipeline`, workflow edits, `pause_pipeline`).
- **[manual]** — the user does it (GitHub secrets, connection `profiles.yml`, environment variables when no MCP tool is available).

Consolidation (🔀 rows): pick the pipeline that runs scheduled production as the keeper, fold the
CI parametrisation into it, repoint the GHA workflow, then offer to pause the old pipeline. For
anything beyond a single CI-only duplicate, hand off to **merge-duplicate-pipelines**. Never pause,
delete, or remove a workflow without a per-item yes. Retiring a manual manifest export is optional:
say what it does now and let the user decide.

## Report shape

```markdown
## Slim CI audit — <n> gaps, <n> conflicts

**Fix first:** <one line, highest-impact gap and its consequence>

| Component | Status | Evidence → consequence |
|-----------|--------|------------------------|
| <only ⚠️ / ❌ / 🔀 rows; collapse ✅ into the line below> |

Already in place: <comma-separated ✅ components>

### Plan
1. [agent, approval] <action> — <what it enables>
2. [manual] <action> — <what stays missing until done>

Proceed with step 1?
```

Aim for under a page. Skip the table when nothing is wrong and go straight to verification.
