# Orchestra reference docs

Grouped by concern. Paths below are relative to `references/orchestra/` in this repo; from a generated skill folder under `.claude/skills/<name>/` or `.cursor/skills/<name>/`, prefix with `../../../references/orchestra/`.

## Pipeline (authoring, runs, failures, remediation, memory)

| File | Purpose |
|------|---------|
| `pipeline/yaml-authoring.md` | Schema, integrations, variables, validation (`create-orchestra-pipeline`) |
| `pipeline/examples.md` | Multi-stage pipeline patterns (warehouse → LLM → messaging, agents) |
| `pipeline/diagnosis-patterns.md` | Classify failures by integration and log signals |
| `pipeline/remediation-playbooks.md` | Action paths by error category |
| `pipeline/knowledge-store.md` | Workspace-specific fix history and failure profile (append-only) |

## MCP (connecting & tool usage)

| File | Purpose |
|------|---------|
| `mcp-playbook.md` | Documentation + Orchestra MCP sequence (read + tool order) |
| `mcp/setup.md` | Install and configure the Orchestra MCP server (`mcp.json`, API key) |
| `mcp/tools-quick-ref.md` | MCP tool names, arguments, and usage notes |

## API (REST exception only)

| File | Purpose |
|------|---------|
| `api/rest-pipeline-yaml.md` | Allowed **read-only** REST fallback: `GET /pipelines/{alias_or_id}/yaml` |

There is **no separate knowledge store for MCP or REST**: operational memory is pipeline-centric. Connection or tooling notes belong in commits to this repo or your global Claude config — not in `pipeline/knowledge-store.md`.
