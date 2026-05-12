# Completion report and troubleshooting

## Completion report template

```markdown
## Slim CI setup summary

### Context
- dbt repo: <org/repo> (default branch: <branch>)
- Pipeline: <id> / <alias> | dbt task: <task_id>
- Pipeline YAML: <path> (<same repo | separate repo>)
- Storage: <Git-backed | Orchestra-backed>

### Already configured
- <bullets or "none">

### Changes made
- `<path>`: <reason>

### Slim CI command
- `dbt_command` passed to Orchestra: <exact string>
- Excludes / targets: <ci target, tag excludes, etc.>
- GHA environments: PR → <Orchestra env> | merge → <Orchestra env>

### Bootstrap: latest_production
- Status: <ready | needs first successful prod run on default branch>
- Notes: <production_run_identifier if set>

### Manual follow-up
| Item | Status |
|------|--------|
| ORCHESTRA_API_KEY in GitHub | <done / pending> |
| Other secrets | <list> |
| dbt connection / CI target in Orchestra | <done / pending> |

### Validation
- `validate_pipeline`: <pass / skip / fail>
- `dbt parse`: <pass / skip / fail>
- Smoke `start_pipeline`: <not run / pass / fail>

### How to test
- Open PR touching `<paths>` or run `workflow_dispatch` on `<workflow file>`.
- Expect check: `<job name>`; Orchestra run link appears in Action logs.

### Failures after merge
- Use **pr-slim-ci-orchestra-debug** for triage.
```

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

**Fix:** Use semicolon-separated commands in one `dbt_command` input (incremental full-refresh tranche, then `state:modified+` with excludes). See `templates/github-dbt-slim-ci-incremental.yml`.
