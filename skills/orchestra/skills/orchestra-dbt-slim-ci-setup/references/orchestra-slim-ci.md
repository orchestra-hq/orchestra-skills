# Orchestra Slim CI — reference index

Consolidated pointers for **orchestra-dbt-slim-ci-setup**. Detail lives in sibling files under `references/` and `templates/`.

## Documentation URLs

| Topic | URL |
|-------|-----|
| CI/CD for dbt Core (Slim CI, latest_production) | https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd |
| GitHub Actions + run-pipeline | https://docs.getorchestra.io/docs/git-control-and-ci-cd/ci-cd/github_actions |
| dbt Core execute task parameters | https://docs.getorchestra.io/docs/integrations/dbt_core/dbt_core_execute |
| Pipeline inputs | https://docs.getorchestra.io/docs/core-concepts/variables/inputs |
| dbt Core in Orchestra (Git, profiles) | https://docs.getorchestra.io/docs/guides/dbt-core/orchestra-setup |
| Pipeline YAML schema | https://docs.getorchestra.io/docs/core-concepts/pipelines/schema |

## Skill files

| File | Purpose |
|------|---------|
| [inputs-matrix.md](inputs-matrix.md) | Must-have / discoverable / manual inputs |
| [audit-existing-setup.md](audit-existing-setup.md) | Find earlier attempts, gap table, consolidation plan |
| [retrofit-checklist.md](retrofit-checklist.md) | Pipeline inventory and YAML patches |
| [mcp-playbook.md](../../../references/orchestra/mcp-playbook.md) | Documentation + Orchestra MCP sequence |
| [completion-report.md](completion-report.md) | Report template and troubleshooting |

## Templates

| File | Purpose |
|------|---------|
| [../templates/pipeline-inputs-snippet.yml](../templates/pipeline-inputs-snippet.yml) | Pipeline inputs + dbt task parameters |
| [../templates/github-dbt-slim-ci.yml](../templates/github-dbt-slim-ci.yml) | GHA workflow: PR Slim CI, deploy on merge, CI schema clean-up |
| [../templates/github-dbt-slim-ci-incremental.yml](../templates/github-dbt-slim-ci-incremental.yml) | Incremental variant: `dbt clone` + `modified_incremental` selector |
| [../templates/dbt/generate_schema_name.sql](../templates/dbt/generate_schema_name.sql) | Per-PR `ci_<PR number>` schema routing |
| [../templates/dbt/drop_ci_schema.sql](../templates/dbt/drop_ci_schema.sql) | Drop the PR's CI schema on close |
| [../templates/dbt/selectors.yml](../templates/dbt/selectors.yml) | `modified_incremental` selector |

## Architecture (one pipeline)

```mermaid
flowchart LR
  subgraph gitCI [GitCI]
    PR[PR_or_push]
    GHA[GitHubActions_run_pipeline]
  end
  subgraph orch [Orchestra]
    Pipe[Production_dbt_pipeline]
    State[latest_production_artifacts]
    Task[DBT_CORE_EXECUTE_task]
  end
  subgraph dbt [dbt]
    Branch[PR_branch_code]
    Slim["build_s_state_modified_defer"]
  end
  PR --> GHA
  GHA -->|"runInputs_dbt_branch_dbt_command_env"| Pipe
  Pipe --> State
  State --> Task
  GHA --> Branch
  Branch --> Task
  Task --> Slim
```

## Companion

Post-setup CI failures: **pr-slim-ci-orchestra-debug** (do not merge into this skill).
