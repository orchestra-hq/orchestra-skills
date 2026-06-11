# Orchestra REST — pipeline YAML (read-only fallback)

The pipeline skills prefer **Orchestra MCP** for everything. The **single** allowed direct Orchestra REST call is fetching pipeline definition as YAML when MCP cannot return the full definition.

## Endpoint

```
GET /pipelines/{alias_or_id}/yaml
```

- `{alias_or_id}` — pipeline UUID or alias string.
- Authenticate with the same Orchestra API key you use for MCP (typically `Authorization: Bearer <token>`; follow your HTTP client / OpenAPI conventions).

## Rules

1. **Read-only.** Do not use REST for listing runs, task runs, logs, artifacts, operations, retries, or pipeline updates.
2. **Narrow scope.** If MCP exposes an equivalent capability in the future, prefer MCP instead of this endpoint.
3. **Git-backed pipelines** — YAML from the API may reflect the synced definition; code fixes still belong in the repository.
