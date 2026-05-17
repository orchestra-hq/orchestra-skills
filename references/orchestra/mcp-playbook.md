# Orchestra MCP playbook

Read tool schemas under the Orchestra Documentation and Orchestra MCP servers before each call.

## Orchestra Documentation MCP

**Server:** `user-Orchestra Documentation`

| Tool | Use |
|------|-----|
| `search_orchestra_documentation` | Broad queries: Slim CI, `latest_production`, `run-pipeline`, `state:modified`, defer |
| `query_docs_filesystem_orchestra_documentation` | Full pages: `dbt_ci_cd.mdx`, `github_actions.mdx`, `dbt_core_execute.mdx`, `inputs.mdx` |

Example filesystem reads:

- `head -200 /docs/git-control-and-ci-cd/ci-cd/dbt_ci_cd.mdx`
- `head -120 /docs/git-control-and-ci-cd/ci-cd/github_actions.mdx`
- `head -80 /docs/integrations/dbt_core/dbt_core_execute.mdx`

Prefer targeted `rg` / `head` over full `cat` (30KB truncation).

## Orchestra MCP (workspace API)

**Server:** `user-Orchestra MCP Server`

| Order | Tool | When |
|-------|------|------|
| 1 | `list_pipelines` | Resolve pipeline id / alias |
| 2 | `validate_pipeline` | After editing JSON/YAML definition (Orchestra-backed or pre-commit check) |
| 3 | `import_pipeline` | Greenfield Git import only (not default retrofit) |
| 4 | `create_pipeline` / `update_pipeline` | **Orchestra-backed only**; never for Git-backed |
| 5 | `start_pipeline` | Optional smoke test with `runInputs` (`dbt_branch`, `dbt_command`) — **user approval** |

Do not use `update_pipeline` on Git-backed pipelines.

## Guardrails

- Cite doc URLs from MCP results; do not invent `latest_production` behavior.
- One production pipeline for prod + Slim CI unless user opts out.
- No secrets in committed YAML or workflow files.
- `start_pipeline` touches the warehouse; default to `validate_pipeline` + `dbt parse` only.

## Non-GitHub CI (follow-up)

Trigger same pipeline via HTTP `POST .../pipelines/{id}/start` with `runInputs` or Orchestra CLI. Document only if user expands scope.

