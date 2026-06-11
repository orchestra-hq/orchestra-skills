# Orchestra MCP Server Setup

When the Orchestra MCP server is not connected, use this reference to connect it before proceeding with Orchestra pipeline skills (`create-orchestra-pipeline`, `fix-orchestra-pipeline`, `triage-orchestra-pipeline`).

These skills use Orchestra's **cloud (hosted) MCP server** — no local install, clone, or runtime needed. See the docs: https://docs.getorchestra.io/docs/mcp

## Prerequisites

- An Orchestra API key (Orchestra UI → workspace Settings → API Keys)

## Cloud MCP endpoint

```
https://mcp.getorchestra.io/orchestra
```

Transport: HTTP. Authenticate with the header `Authorization: Bearer <your-orchestra-api-key>`.

## Claude Code configuration

The quickest path is the CLI:

```bash
claude mcp add orchestra https://mcp.getorchestra.io/orchestra \
  --transport http \
  --header "Authorization: Bearer <YOUR_ORCHESTRA_API_KEY>"
```

Or add it to your MCP config (e.g. `~/.claude/mcp.json`, global so it's available in all projects):

```json
{
  "mcpServers": {
    "orchestra": {
      "url": "https://mcp.getorchestra.io/orchestra",
      "headers": {
        "Authorization": "Bearer <YOUR_ORCHESTRA_API_KEY>"
      }
    }
  }
}
```

Replace `<YOUR_ORCHESTRA_API_KEY>` with your key. Each workspace needs its own MCP connection with workspace-specific credentials.

## Verify the server is connected

After saving settings, restart Claude Code (or run `/hooks` to reload config). Then confirm the Orchestra MCP tools appear — you should see tools like `list_pipeline_runs`, `list_task_runs`, etc. If they don't, check the API key and that the URL/header are correct.

## Prompting the user

If the MCP server is not connected at the start of a fix session, say:

> The Orchestra MCP server isn't connected. To set it up:
> 1. Add the cloud MCP server: `claude mcp add orchestra https://mcp.getorchestra.io/orchestra --transport http --header "Authorization: Bearer <YOUR_ORCHESTRA_API_KEY>"` (or add the JSON block above to `~/.claude/mcp.json`)
> 2. Set your Orchestra API key in the `Authorization` header
> 3. Restart Claude Code or run `/hooks` to reload
>
> Alternatively, paste a pipeline run URL, error message, or run ID and I'll diagnose from that instead.

Self-hosting the MCP server is available via the [orchestra-mcp](https://github.com/orchestra-hq/orchestra-mcp) repo for organizations with IP restrictions — see the docs above.
