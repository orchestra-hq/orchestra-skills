# Orchestra reference docs

Grouped by concern. Paths below are relative to `references/orchestra/` in this repo; from a skill folder under `skills/<name>/`, reach them with `../../references/orchestra/`.

## Pipeline (authoring, runs, failures, remediation, memory)

| File | Purpose |
|------|---------|
| `pipeline/yaml-authoring.md` | Schema, integrations, variables, validation (`create-orchestra-pipeline`) |
| `pipeline/examples.md` | Multi-stage pipeline patterns (warehouse → LLM → messaging, agents) |
| `pipeline/diagnosis-patterns.md` | Classify failures by integration and log signals |
| `pipeline/remediation-playbooks.md` | Action paths by error category |
| `pipeline/knowledge-store.md` | Optional local fix-history template (ships empty); recall/record is deferred to your client's persistent memory |

## State-aware orchestration (dbt SAO)

| File | Purpose |
|------|---------|
| `dbt-sao/README.md` | Index + the per-warehouse freshness rule that decides everything |
| `dbt-sao/source-freshness.md` | dbt `freshness` schema, version placement, `loaded_at_field`/`loaded_at_query` (`configure-dbt-source-freshness`) |
| `dbt-sao/build-after.md` | dbt model `config.freshness.build_after` schema (`configure-dbt-build-after`) |
| `dbt-sao/orchestra-task.md` | Enabling `use_state_orchestration` on the dbt Core task (Git- vs Orchestra-backed) |
| `dbt-sao/warehouses/*.md` | Per-warehouse freshness specifics (Snowflake, BigQuery, Databricks, MotherDuck) |

## MCP (connecting & tool usage)

| File | Purpose |
|------|---------|
| `mcp-playbook.md` | Documentation + Orchestra MCP sequence (read + tool order) |
| `mcp/tools-quick-ref.md` | MCP tool names, arguments, and usage notes |

There is **no separate knowledge store for MCP**: operational memory is pipeline-centric. Connection or tooling notes belong in commits to this repo or your global Claude config — not in `pipeline/knowledge-store.md`.
