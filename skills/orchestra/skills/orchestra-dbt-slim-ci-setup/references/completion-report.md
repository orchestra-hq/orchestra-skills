# Completion report and troubleshooting

## Completion report template

```markdown
## Slim CI — <enabled | partially enabled>

**Enabled:** <comma-separated: PR checks on <paths>, per-PR schema ci_<n>, deploy on merge, clean-up, per-env concurrency, incremental variant>
**Still missing:** <one line each, with the consequence, or "nothing">
**Retired / consolidated:** <pipelines paused, workflows removed, or "none">

### You need to
1. <manual step, e.g. add ORCHESTRA_API_KEY to GitHub secrets>
2. <...>

### Changed
- `<path or pipeline>`: <one-line reason>

### Check it works
Open a PR touching `<paths>`; expect the `<job name>` check with an Orchestra run link in its log.
Validation: `validate_pipeline` <pass/skip>, `dbt parse` <pass/skip>, smoke run <not run/pass>.
```

Omit empty lines. `latest_production` not yet populated goes under **Still missing** with "run prod once on the default branch".

## Troubleshooting

### Empty or missing `latest_production`

**Symptoms:** Slim CI fails on state/defer; docs note folder empty or missing.

**Fix:** Run the production dbt task successfully on the **default branch** with a normal prod command (no defer). Confirm task completes on default branch. Re-run Slim CI.

### Wrong baseline branch

**Symptoms:** `state:modified` selects unexpected nodes.

**Fix:** Set `production_run_identifier` on the dbt task to the intended branch or commit SHA (not tags). Ensure default branch in Git matches Orchestra expectation.

### CI target / profile mismatch

**Symptoms:** `dbt` errors on unknown target; workflow passes `--target ci` but Orchestra connection lacks that output.

**Fix:** Add `ci` (and `prod` if used) to Orchestra-uploaded `profiles.yml` or change workflow/command to match existing targets. Align macros (e.g. schema naming for `ci`).

### Separate pipeline repo confusion

**Symptoms:** Pipeline runs wrong YAML or wrong dbt branch.

**Fix:** Action `branch` = pipeline YAML repo branch. `run_inputs.dbt_branch` = PR head for dbt checkout only.

### Git-backed pipeline edited only in Orchestra UI

**Symptoms:** Drift; CI uses stale YAML.

**Fix:** Source of truth is Git; commit YAML and merge. Do not rely on `update_pipeline` MCP for Git-backed pipelines.

### Environment name case

**Symptoms:** Action succeeds but wrong Orchestra environment or connection.

**Fix:** Orchestra environment names are case-sensitive; match GHA `environment` to Orchestra exactly.

### Multi-command `dbt_command`

**Symptoms:** Incremental models need full refresh when modified.

**Fix:** Use semicolon-separated commands in one `dbt_command` input: `dbt clone`, full-refresh `--selector modified_incremental`, then `state:modified+`. Each chained command after the first starts with `dbt`, and each carries its own `--target`. See `templates/github-dbt-slim-ci-incremental.yml`.

### Superseded PR runs overwrite each other

**Symptoms:** Two Orchestra runs build into the same `ci_<PR number>` schema after a new push.

**Fix:** `cancel_on_exit: true` on the PR job, with `orchestra-hq/run-pipeline@v1.7.0` or later.

### PR runs SKIPPED

**Symptoms:** GHA check passes but Orchestra run is `SKIPPED`.

**Fix:** Concurrency limit hit. Use `max_active: ${{ ENV.DBT_PIPELINE_CONCURRENCY }}` with a higher value in the CI environment.

### `env_var('DBT_CI_SCHEMA_SUFFIX')` not set

**Symptoms:** dbt compile error on the `ci` target.

**Fix:** Task `environment_variables` must map `DBT_CI_SCHEMA_SUFFIX` from `inputs.dbt_ci_schema_suffix`, and the PR / clean-up jobs must pass `dbt_ci_schema_suffix`.

### CI schema clean-up fails

**Symptoms:** `drop_ci_schema` not found, or fork PRs fail.

**Fix:** The macro must be on the default branch (clean-up runs with `dbt_branch: main`). Fork PRs cannot read secrets; the template skips them.
