# Enabling SAO on the Orchestra dbt Core task

dbt-side freshness and `build_after` config is inert until Orchestra is told to consume it. That
switch is a single parameter on the dbt Core task:

```yaml
parameters:
  use_state_orchestration: true
```

The task is `integration: DBT_CORE`, `integration_job: DBT_CORE_EXECUTE`. In the Orchestra UI
this is the **"Use state orchestration"** toggle in the dbt Core task's parameters. No package
upgrade or extra command flags are needed — it works on plain `dbt build`.

**It's the SAO master switch, not a per-feature setting.** `use_state_orchestration` turns
state-aware orchestration on for the task as a whole — Orchestra then consumes *whatever* SAO
config exists in the project: source freshness **and** `build_after` together. It is not specific
to either one. So both the `configure-dbt-source-freshness` and `configure-dbt-build-after` skills
just need it to be **on** (a shared prerequisite); neither "owns" it. If it's already enabled
because the other half of SAO was set up first, that's expected — confirm and move on, don't toggle
it per feature.

> Not the same as Slim CI. Slim CI uses `state:modified+` and `--defer` via
> `production_run_identifier` and does **not** require `use_state_orchestration`. SAO
> (freshness / `build_after`) is a separate mechanism. Don't add `use_state_orchestration` to a
> Slim CI setup, and don't add Slim CI params here.

## How to apply the flag — depends on how the pipeline is stored

First read the pipeline (`get_pipeline`, or the MCP playbook at `../mcp-playbook.md`) and find
the dbt Core task. Then:

### Git-backed pipeline (YAML lives in the repo)

Edit the task's `parameters` in the pipeline YAML file and **commit**. Do **not** call
`update_pipeline` — Git is the source of truth and an MCP update would be overwritten on the next
sync. Add `use_state_orchestration: true` alongside the existing dbt params:

```yaml
Run_dbt_build:
  integration: DBT_CORE
  integration_job: DBT_CORE_EXECUTE
  parameters:
    commands: "dbt build"
    package_manager: UV
    python_version: "3.12"
    project_dir: "dbt_projects/analytics"
    use_state_orchestration: true        # <- add this
  depends_on: []
  name: "Run dbt build"
```

### Orchestra-backed pipeline (managed in Orchestra, no repo YAML)

`validate_pipeline`, then update via MCP. If `update_pipeline` returns a `422 extra_forbidden`
on `storage_provider`, use `migrate_pipeline` instead — this is a known REST quirk.

## Confirm before flipping

If the dbt task already has `use_state_orchestration: true`, say so and don't re-apply. Report
the change (or no-op) in the handoff so the user knows SAO is actually live.

## Resetting state

If the user wants the next run to behave like a full refresh: Orchestra UI →
Settings → Workspace → Asset management → **Purge state**. Debug logging for SAO decisions:
set env var `ORCHESTRA_DBT_DEBUG=true` on the task.
