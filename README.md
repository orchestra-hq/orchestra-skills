# orchestra-skills

Agent skills and reference docs for diagnosing, fixing, and triaging [Orchestra](https://www.getorchestra.io/) data pipelines with an AI assistant. The workflows assume the [Orchestra MCP server](https://github.com/orchestra-hq/orchestra-mcp) is connected so the agent can list runs, fetch logs and artifacts, and retry pipelines from your workspace.

## What is in this repo

| Path | Purpose |
|------|---------|
| [`.claude/skills/`](.claude/skills/) | Executable skill workflows (`SKILL.md` per skill) |
| [`.claude/references/orchestra/`](.claude/references/orchestra/) | Shared diagnosis, remediation, MCP, and API reference material |
| [`AGENTS.md`](AGENTS.md) | Short orientation for coding agents working in this repository |

### Skills

| Skill | Use when |
|-------|----------|
| [`fix-orchestra-pipeline`](.claude/skills/fix-orchestra-pipeline/SKILL.md) | A pipeline or task failed and you want end-to-end diagnosis, fixes, retry, and learning from past fixes |
| [`triage-orchestra-pipeline`](.claude/skills/triage-orchestra-pipeline/SKILL.md) | You want a fix prepared on a branch with validation, then a human review gate before merge |

Both skills are MCP-first: use Orchestra MCP tools for runs, logs, artifacts, and retries. The only documented REST exception is read-only pipeline YAML when MCP cannot return the full definition ([`api/rest-pipeline-yaml.md`](.claude/references/orchestra/api/rest-pipeline-yaml.md)).

### Reference library

Start at [`.claude/references/orchestra/README.md`](.claude/references/orchestra/README.md). Highlights:

- **Pipeline** — error patterns, remediation playbooks, append-only workspace fix history ([`knowledge-store.md`](.claude/references/orchestra/pipeline/knowledge-store.md))
- **MCP** — server setup and tool quick reference
- **API** — allowed read-only REST fallback for pipeline YAML

## Install for humans

### Prerequisites

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/)
- An Orchestra API key (Orchestra UI → Settings → API Keys)
- A clone of [orchestra-mcp](https://github.com/orchestra-hq/orchestra-mcp) and MCP configuration (see [`.claude/references/orchestra/mcp/setup.md`](.claude/references/orchestra/mcp/setup.md))

### Claude Code

1. Clone this repository.
2. Register the skills directory with Claude Code (project-local or global), or copy or symlink the skill folders you need into your skills path.
3. Configure the Orchestra MCP server in `~/.claude/mcp.json` using the setup guide above.
4. Restart Claude Code or reload MCP so tools such as `list_pipeline_runs` and `list_task_run_logs` appear.

### Cursor

1. Clone this repository (or add it as a workspace).
2. Point Cursor at the skills under [`.claude/skills/`](.claude/skills/), or copy or symlink them into [`.cursor/skills/`](.cursor/skills/) if you want project-scoped discovery.
3. Connect the Orchestra MCP server in Cursor MCP settings with the same `uv` command and `ORCHESTRA_API_KEY` as in the setup guide.
4. For agent behavior in this repo, read [`AGENTS.md`](AGENTS.md).

## Typical workflows

**Failed run** — Paste a pipeline run URL, run UUID, pipeline name, or error snippet. The fix skill parses the input, loads failed task runs, pulls logs and artifacts, classifies the failure, applies remediation, retries when appropriate, and appends to the knowledge store.

**Review before merge** — Use the triage skill when you want a branch fix, validation run, and triage summary, then explicit approval before merge and production retry.

**Downstream symptom** — Triage can start from a downstream issue (stale dashboard, bad dbt output) and walk upstream through the pipeline graph.

## Contributing

- Keep shared Orchestra material under `.claude/references/orchestra/`; skills should link there instead of duplicating long playbooks.
- After a successful fix, append to [`pipeline/knowledge-store.md`](.claude/references/orchestra/pipeline/knowledge-store.md) and extend [`pipeline/diagnosis-patterns.md`](.claude/references/orchestra/pipeline/diagnosis-patterns.md) when you discover a new pattern.
- Do not commit API keys, `.env` files, or other secrets.

Agents editing this repo should follow [`AGENTS.md`](AGENTS.md).
