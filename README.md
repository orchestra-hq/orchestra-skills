# orchestra-skills

Agent skills and reference docs for diagnosing, fixing, and triaging [Orchestra](https://www.getorchestra.io/) data pipelines with an AI assistant. The workflows assume the [Orchestra MCP server](https://github.com/orchestra-hq/orchestra-mcp) is connected so the agent can list runs, fetch logs and artifacts, and retry pipelines from your workspace.

## What is in this repo

| Path | Purpose |
|------|---------|
| [`skills/`](skills/) | The skills — one `SKILL.md` per skill, plus any `references/`/`templates/` it needs. Single source of truth. |
| [`references/orchestra/`](references/orchestra/) | Shared diagnosis, remediation, MCP, and API reference material |
| [`AGENTS.md`](AGENTS.md) | Short orientation for coding agents working in this repository |
| [`docs/`](docs/) | Repo plans, including the [plugin-marketplace migration plan](docs/marketplace-migration-plan.md) |

### Skills

Each skill auto-triggers when your prompt matches it — just describe the problem in natural language. The "Try saying" column shows a prompt that activates each one.

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`fix-orchestra-pipeline`](skills/fix-orchestra-pipeline/SKILL.md) | Diagnose → fix → retry a failed pipeline end-to-end (logs, artifacts, root cause, PR, rerun). | _"Why did my pipeline fail?"_ — or paste a run URL, UUID, or error |
| [`triage-orchestra-pipeline`](skills/triage-orchestra-pipeline/SKILL.md) | Same diagnosis, but opens a fix PR and validates it on a branch, then **stops for your approval** before merging. | _"Triage my pipeline but don't merge yet"_ |
| [`create-orchestra-pipeline`](skills/create-orchestra-pipeline/SKILL.md) | Author, validate, and remediate a `version: v1` pipeline YAML from a description. | _"Create a pipeline that runs dbt then loads Snowflake"_ |
| [`orchestra-dbt-slim-ci-setup`](skills/orchestra-dbt-slim-ci-setup/SKILL.md) | Retrofit dbt Slim CI (`run-pipeline`, `latest_production`, `state:modified+`, `--defer`) onto an existing production dbt pipeline. | _"Set up dbt Slim CI in Orchestra"_ |

**To get going:** connect the [Orchestra MCP server](https://github.com/orchestra-hq/orchestra-mcp) (see [Install](#install-for-humans) below), make the skills discoverable by your client (see Install), then just ask. All pipeline skills are MCP-first — runs, logs, artifacts, retries, and validation go through MCP tools. The only documented REST exception is read-only pipeline YAML when MCP cannot return the full definition ([`api/rest-pipeline-yaml.md`](references/orchestra/api/rest-pipeline-yaml.md)).

### Reference library

Start at [`references/orchestra/README.md`](references/orchestra/README.md). Highlights:

- **Pipeline** — authoring schema + examples, failure classification, remediation playbooks, and an optional local fix-history template ([`knowledge-store.md`](references/orchestra/pipeline/knowledge-store.md))
- **MCP** — server setup and tool quick reference
- **API** — allowed read-only REST fallback for pipeline YAML

## Install for humans

### Prerequisites

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/)
- An Orchestra API key (Orchestra UI → Settings → API Keys)
- A clone of [orchestra-mcp](https://github.com/orchestra-hq/orchestra-mcp) and MCP configuration (see [`references/orchestra/mcp/setup.md`](references/orchestra/mcp/setup.md))

1. Clone this repository.
2. Configure the Orchestra MCP server (`~/.claude/mcp.json` for Claude Code, or Cursor MCP settings) using the setup guide above, with your `ORCHESTRA_API_KEY`. Restart/reload so tools such as `list_pipeline_runs` and `list_task_run_logs` appear.
3. Make the skills discoverable by your client. The skills live in [`skills/`](skills/) as the single source. Packaged Claude Code / Cursor distribution via the plugin marketplace is planned — see the [migration plan](docs/marketplace-migration-plan.md). Until then, point your client at a skill directly: e.g. for Claude Code, symlink or copy `skills/<name>` into `.claude/skills/`, or register `skills/` as a skills source.
4. For agent behavior in this repo, read [`AGENTS.md`](AGENTS.md).

## Typical workflows

**Failed run** — Paste a pipeline run URL, run UUID, pipeline name, or error snippet. The fix skill parses the input, loads failed task runs, pulls logs and artifacts, classifies the failure, applies remediation, retries when appropriate, and optionally records the fix to your client's memory.

**Author pipeline YAML** — Describe the desired stages/tasks and create a `version: v1` pipeline YAML. The authoring skill validates (via `orchestra-cli` or MCP) and remediates validation errors until clean.

**Review before merge** — Use the triage skill when you want a branch fix, validation run, and triage summary, then explicit approval before merge and production retry.

**Downstream symptom** — Triage can start from a downstream issue (stale dashboard, bad dbt output) and walk upstream through the pipeline graph.

## Contributing

- Skills live under [`skills/`](skills/) and shared Orchestra material under [`references/orchestra/`](references/orchestra/). There is a single skill tree — no generated copies to keep in sync.
- To add a skill, create `skills/<skill-name>/SKILL.md` with `name` + `description` frontmatter, put any supporting `references/`/`templates/` in the same folder, and add it to the [Skills](#skills) table. CI (`Validate Skills`) checks the frontmatter and that `SKILL.md` stays under ~500 lines. Write skills to be client-agnostic — describe capabilities (e.g. "if your client can schedule a wake-up…") rather than naming a specific tool.
- Recording fixes is optional and deferred to your client's persistent memory — never commit workspace-specific fix history. Extend [`pipeline/diagnosis-patterns.md`](references/orchestra/pipeline/diagnosis-patterns.md) only with generic, reusable patterns.
- Do not commit API keys, `.env` files, or other secrets.

Agents editing this repo should follow [`AGENTS.md`](AGENTS.md).
