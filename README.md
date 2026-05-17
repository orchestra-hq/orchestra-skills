# orchestra-skills

Agent skills and reference docs for diagnosing, fixing, and triaging [Orchestra](https://www.getorchestra.io/) data pipelines with an AI assistant. The workflows assume the [Orchestra MCP server](https://github.com/orchestra-hq/orchestra-mcp) is connected so the agent can list runs, fetch logs and artifacts, and retry pipelines from your workspace.

## What is in this repo

| Path | Purpose |
|------|---------|
| [`skills/`](skills/) | Canonical skill source (`SKILL.md` per skill; optional `claude.md` / `cursor.md`) |
| [`.claude/skills/`](.claude/skills/) | Generated Claude Code skill discovery |
| [`.cursor/skills/`](.cursor/skills/) | Generated Cursor skill discovery |
| [`references/orchestra/`](references/orchestra/) | Shared diagnosis, remediation, MCP, and API reference material |
| [`AGENTS.md`](AGENTS.md) | Short orientation for coding agents working in this repository |

### Skills
| Skill | Use when | Claude | Cursor |
|-------|----------|--------|--------|
| `create-orchestra-pipeline` | You want to author a new Orchestra `version: v1` pipeline YAML, validate it, and remediate validation errors | [`.claude/skills/create-orchestra-pipeline/SKILL.md`](.claude/skills/create-orchestra-pipeline/SKILL.md) | [`.cursor/skills/create-orchestra-pipeline/SKILL.md`](.cursor/skills/create-orchestra-pipeline/SKILL.md) |
| `fix-orchestra-pipeline` | A pipeline or task failed and you want end-to-end diagnosis, fixes, retry, and learning from past fixes | [`.claude/skills/fix-orchestra-pipeline/SKILL.md`](.claude/skills/fix-orchestra-pipeline/SKILL.md) | [`.cursor/skills/fix-orchestra-pipeline/SKILL.md`](.cursor/skills/fix-orchestra-pipeline/SKILL.md) |
| `triage-orchestra-pipeline` | You want a fix prepared on a branch with validation, then a human review gate before merge | [`.claude/skills/triage-orchestra-pipeline/SKILL.md`](.claude/skills/triage-orchestra-pipeline/SKILL.md) | [`.cursor/skills/triage-orchestra-pipeline/SKILL.md`](.cursor/skills/triage-orchestra-pipeline/SKILL.md) |

All pipeline skills are MCP-first: use Orchestra MCP tools for runs, logs, artifacts, retries, and (for YAML authoring) pipeline validation when available. The only documented REST exception is read-only pipeline YAML when MCP cannot return the full definition ([`api/rest-pipeline-yaml.md`](references/orchestra/api/rest-pipeline-yaml.md)).

### Reference library

Start at [`references/orchestra/README.md`](references/orchestra/README.md). Highlights:

- **Pipeline** — authoring schema + examples, failure classification, remediation playbooks, and append-only workspace fix history ([`knowledge-store.md`](references/orchestra/pipeline/knowledge-store.md))
- **MCP** — server setup and tool quick reference
- **API** — allowed read-only REST fallback for pipeline YAML

## Install for humans

### Prerequisites

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/)
- An Orchestra API key (Orchestra UI → Settings → API Keys)
- A clone of [orchestra-mcp](https://github.com/orchestra-hq/orchestra-mcp) and MCP configuration (see [`references/orchestra/mcp/setup.md`](references/orchestra/mcp/setup.md))

### Claude Code

1. Clone this repository.
2. Open the repo in Claude Code so project skills under [`.claude/skills/`](.claude/skills/) are discovered, or register that directory globally.
3. Configure the Orchestra MCP server in `~/.claude/mcp.json` using the setup guide above.
4. Restart Claude Code or reload MCP so tools such as `list_pipeline_runs` and `list_task_run_logs` appear.

### Cursor

1. Clone this repository (or add it as a workspace).
2. Use the committed skills under [`.cursor/skills/`](.cursor/skills/) for project-scoped discovery.
3. Connect the Orchestra MCP server in Cursor MCP settings with the same `uv` command and `ORCHESTRA_API_KEY` as in the setup guide.
4. For agent behavior in this repo, read [`AGENTS.md`](AGENTS.md).

## Typical workflows

**Failed run** — Paste a pipeline run URL, run UUID, pipeline name, or error snippet. The fix skill parses the input, loads failed task runs, pulls logs and artifacts, classifies the failure, applies remediation, retries when appropriate, and appends to the knowledge store.

**Author pipeline YAML** — Describe the desired stages/tasks and create a `version: v1` pipeline YAML. The authoring skill validates (via `orchestra-cli` or MCP) and remediates validation errors until clean.

**Review before merge** — Use the triage skill when you want a branch fix, validation run, and triage summary, then explicit approval before merge and production retry.

**Downstream symptom** — Triage can start from a downstream issue (stale dashboard, bad dbt output) and walk upstream through the pipeline graph.

## Contributing

- Edit canonical skills under [`skills/`](skills/) and shared Orchestra material under [`references/orchestra/`](references/orchestra/); do not hand-edit generated trees under `.claude/skills/` or `.cursor/skills/`.
- After changing skills, run `python scripts/sync_skills.py` and commit the regenerated outputs.
- To add a skill, create `skills/<skill-name>/SKILL.md`, add optional `claude.md` / `cursor.md` for platform-specific steps, run sync, and commit canonical plus generated folders.
- After a successful fix, append to [`pipeline/knowledge-store.md`](references/orchestra/pipeline/knowledge-store.md) and extend [`pipeline/diagnosis-patterns.md`](references/orchestra/pipeline/diagnosis-patterns.md) when you discover a new pattern.
- Do not commit API keys, `.env` files, or other secrets.

Agents editing this repo should follow [`AGENTS.md`](AGENTS.md).
