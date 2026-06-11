# Orchestra MCP Server Setup

When the Orchestra MCP server is not connected, use this reference to set it up before proceeding with Orchestra pipeline skills (`create-orchestra-pipeline`, `fix-orchestra-pipeline`, `triage-orchestra-pipeline`).

## Prerequisites

- Python 3.10+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- An Orchestra API key (Orchestra UI → Settings → API Keys)

## Installation

```bash
git clone https://github.com/orchestra-hq/orchestra-mcp.git ~/orchestra-mcp
```

No further install step needed — `uv` handles dependencies at runtime.

## Claude Code configuration

Create `~/.claude/mcp.json` (global, so it's available in all projects):

```json
{
  "mcpServers": {
    "orchestra": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/Users/<you>/orchestra-mcp/orchestramcp",
        "--with",
        "fastmcp",
        "fastmcp",
        "run",
        "server.py"
      ],
      "env": {
        "ORCHESTRA_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

Replace `/Users/<you>/orchestra-mcp` with the actual clone path and `<your-api-key>` with your key.

## Verify the server is connected

After saving settings, restart Claude Code (or run `/hooks` to reload config). Then confirm the Orchestra MCP tools appear — you should see tools like `list_pipeline_runs`, `get_task_runs`, etc.

If tools don't appear, run:
```bash
uv run --project ~/orchestra-mcp/orchestramcp --with fastmcp fastmcp run server.py
```
and check for errors (missing deps, bad API key, wrong path).

## Prompting the user

If the MCP server is not connected at the start of a fix session, say:

> The Orchestra MCP server isn't connected. To set it up:
> 1. Clone the repo: `git clone https://github.com/orchestra-hq/orchestra-mcp.git ~/orchestra-mcp`
> 2. Add the MCP config to `~/.claude/mcp.json` using the JSON block in **Claude Code configuration** above
> 3. Set your `ORCHESTRA_API_KEY` in the config
> 4. Restart Claude Code or run `/hooks` to reload
>
> Alternatively, paste a pipeline run URL, error message, or run ID and I'll diagnose from that instead.
