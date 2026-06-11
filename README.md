# orchestra-skills

Agent skills and reference docs for diagnosing, fixing, and triaging [Orchestra](https://www.getorchestra.io/) data pipelines with an AI assistant. The workflows assume [Orchestra's cloud MCP server](https://docs.getorchestra.io/docs/mcp) is connected so the agent can list runs, fetch logs and artifacts, and retry pipelines from your workspace.

This repo is a **plugin marketplace**: the single `orchestra` plugin bundles every skill and installs into both Claude Code and Cursor from the manifests at the repo root (see [Install](#install-for-humans)).

## What is in this repo

### Skills

Each skill auto-triggers when your prompt matches it — just describe the problem in natural language. The "Try saying" column shows a prompt that activates each one.

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`fix-orchestra-pipeline`](skills/orchestra/skills/fix-orchestra-pipeline/SKILL.md) | Diagnose → fix → retry a failed pipeline end-to-end (logs, artifacts, root cause, PR, rerun). | _"Why did my pipeline fail?"_ — or paste a run URL, UUID, or error |
| [`triage-orchestra-pipeline`](skills/orchestra/skills/triage-orchestra-pipeline/SKILL.md) | Same diagnosis, but opens a fix PR and validates it on a branch, then **stops for your approval** before merging. | _"Triage my pipeline but don't merge yet"_ |
| [`create-orchestra-pipeline`](skills/orchestra/skills/create-orchestra-pipeline/SKILL.md) | Author, validate, and remediate a `version: v1` pipeline YAML from a description. | _"Create a pipeline that runs dbt then loads Snowflake"_ |
| [`orchestra-dbt-slim-ci-setup`](skills/orchestra/skills/orchestra-dbt-slim-ci-setup/SKILL.md) | Retrofit dbt Slim CI (`run-pipeline`, `latest_production`, `state:modified+`, `--defer`) onto an existing production dbt pipeline. | _"Set up dbt Slim CI in Orchestra"_ |
| [`run-snowflake-quality-tests`](skills/orchestra/skills/run-snowflake-quality-tests/SKILL.md) | Inspect Snowflake tables, then build and deploy a data-quality testing pipeline to Orchestra. | _"Run Snowflake data quality tests"_ |

**To get going:** connect [Orchestra's cloud MCP server](https://docs.getorchestra.io/docs/mcp) (see [Install](#install-for-humans) below), install the `orchestra` plugin so the skills are discoverable by your client (see Install), then just ask.

### Reference library

Start at [`skills/orchestra/references/orchestra/README.md`](skills/orchestra/references/orchestra/README.md). Highlights:

- **Pipeline** — authoring schema + examples, failure classification, remediation playbooks, and an optional local fix-history template ([`knowledge-store.md`](skills/orchestra/references/orchestra/pipeline/knowledge-store.md))
- **MCP** — [cloud MCP](https://docs.getorchestra.io/docs/mcp) setup and tool quick reference

## Install for humans

### Prerequisites

- An Orchestra API key (Orchestra UI → Settings → API Keys)

1. **Connect Orchestra's cloud MCP server.** Point your client at the hosted endpoint following the [cloud MCP docs](https://docs.getorchestra.io/docs/mcp) (`~/.claude/mcp.json` for Claude Code, or Cursor MCP settings) and authenticate with your `ORCHESTRA_API_KEY` — no local install required. Restart/reload so tools such as `list_pipeline_runs` and `list_task_run_logs` appear.
2. **Install the `orchestra` plugin** so the skills are discoverable by your client:
   - **Claude Code** — add this repo as a marketplace, then install the plugin:
     ```
     /plugin marketplace add orchestra-hq/orchestra-skills
     /plugin install orchestra@orchestra-marketplace
     ```
     (or point at a local clone: `/plugin marketplace add /path/to/orchestra-skills`).
   - **Cursor** — add the marketplace and install the `orchestra` plugin from `.cursor-plugin/marketplace.json` per [Cursor's plugin docs](https://docs.cursor.com/).
   Each skill auto-triggers from a matching prompt once installed.
3. For agent behavior in this repo, read [`AGENTS.md`](AGENTS.md).

## Typical workflows

**Failed run** — Paste a pipeline run URL, run UUID, pipeline name, or error snippet. The fix skill parses the input, loads failed task runs, pulls logs and artifacts, classifies the failure, applies remediation, retries when appropriate, and optionally records the fix to your client's memory.

**Author pipeline YAML** — Describe the desired stages/tasks and create a `version: v1` pipeline YAML. The authoring skill validates (via `orchestra-cli` or MCP) and remediates validation errors until clean.

**Review before merge** — Use the triage skill when you want a branch fix, validation run, and triage summary, then explicit approval before merge and production retry.

**Downstream symptom** — Triage can start from a downstream issue (stale dashboard, bad dbt output) and walk upstream through the pipeline graph.

## Contributing

- Skills live under [`skills/orchestra/skills/`](skills/orchestra/skills/) and shared Orchestra material under [`skills/orchestra/references/orchestra/`](skills/orchestra/references/orchestra/), all inside the single `orchestra` plugin bundle. There is a single skill tree — no generated copies to keep in sync.
- To add a skill, create `skills/orchestra/skills/<skill-name>/SKILL.md` with `name` + `description` frontmatter, put any supporting `references/`/`templates/` in the same folder, and add it to the [Skills](#skills) table. The `orchestra` plugin exposes it automatically — bump the `version` in `skills/orchestra/.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`. CI (`Validate Skills`) checks the frontmatter, that `SKILL.md` stays under ~500 lines, and that the manifests are valid JSON. Write skills to be client-agnostic — describe capabilities (e.g. "if your client can schedule a wake-up…") rather than naming a specific tool.
- Recording fixes is optional and deferred to your client's persistent memory — never commit workspace-specific fix history. Extend [`pipeline/diagnosis-patterns.md`](skills/orchestra/references/orchestra/pipeline/diagnosis-patterns.md) only with generic, reusable patterns.
- Do not commit API keys, `.env` files, or other secrets.

Agents editing this repo should follow [`AGENTS.md`](AGENTS.md).
