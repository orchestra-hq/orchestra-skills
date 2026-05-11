# Orchestra reference docs

Grouped by concern. Paths below are relative to `.claude/references/orchestra/` in this repo; from either skill folder, prefix with `../../references/orchestra/`.

## Pipeline (runs, failures, remediation, memory)

These describe **what went wrong** in pipelines and **how to fix or record** it:

| File | Purpose |
|------|---------|
| `pipeline/diagnosis-patterns.md` | Classify failures by integration and log signals |
| `pipeline/remediation-playbooks.md` | Action paths by error category |
| `pipeline/knowledge-store.md` | Workspace-specific fix history and failure profile (append-only) |

## MCP (connecting & tool usage)

| File | Purpose |
|------|---------|
| `mcp/setup.md` | Install and configure the Orchestra MCP server (`mcp.json`, API key) |
| `mcp/tools-quick-ref.md` | MCP tool names, arguments, and usage notes |

## API (REST exception only)

| File | Purpose |
|------|---------|
| `api/rest-pipeline-yaml.md` | Allowed **read-only** REST fallback: `GET /pipelines/{alias_or_id}/yaml` |

There is **no separate knowledge store for MCP or REST**: operational memory is pipeline-centric. Connection or tooling notes belong in commits to this repo or your global Claude config — not in `pipeline/knowledge-store.md`.
