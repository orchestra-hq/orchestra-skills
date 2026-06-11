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

Each skill auto-triggers when your prompt matches it — just describe the problem in natural language. The "Try saying" column shows a prompt that activates each one.

| Skill | What it does | Try saying |
|-------|--------------|------------|
| [`fix-orchestra-pipeline`](skills/fix-orchestra-pipeline/SKILL.md) | Diagnose → fix → retry a failed pipeline end-to-end (logs, artifacts, root cause, PR, rerun). | _"Why did my pipeline fail?"_ — or paste a run URL, UUID, or error |
| [`triage-orchestra-pipeline`](skills/triage-orchestra-pipeline/SKILL.md) | Same diagnosis, but opens a fix PR and validates it on a branch, then **stops for your approval** before merging. | _"Triage my pipeline but don't merge yet"_ |
| [`create-orchestra-pipeline`](skills/create-orchestra-pipeline/SKILL.md) | Author, validate, and remediate a `version: v1` pipeline YAML from a description. | _"Create a pipeline that runs dbt then loads Snowflake"_ |
| [`orchestra-dbt-slim-ci-setup`](skills/orchestra-dbt-slim-ci-setup/SKILL.md) | Retrofit dbt Slim CI (`run-pipeline`, `latest_production`, `state:modified+`, `--defer`) onto an existing production dbt pipeline. | _"Set up dbt Slim CI in Orchestra"_ |

Links point to the canonical source; the equivalent generated copies live under [`.claude/skills/`](.claude/skills/) and [`.cursor/skills/`](.cursor/skills/).

**To get going:** connect the [Orchestra MCP server](https://github.com/orchestra-hq/orchestra-mcp) (see [Install](#install-for-humans) below), open this repo in Claude Code or Cursor, then just ask. All pipeline skills are MCP-first — runs, logs, artifacts, retries, and validation go through MCP tools. The only documented REST exception is read-only pipeline YAML when MCP cannot return the full definition ([`api/rest-pipeline-yaml.md`](references/orchestra/api/rest-pipeline-yaml.md)).

### Reference library

Start at [`references/orchestra/README.md`](references/orchestra/README.md). Highlights:

- **Pipeline** — authoring schema + examples, failure classification, remediation playbooks, and an optional local fix-history template ([`knowledge-store.md`](references/orchestra/pipeline/knowledge-store.md))
- **MCP** — server setup and tool quick reference
- **API** — allowed read-only REST fallback for pipeline YAML

## Adding a skill

Skills are authored **once** under `skills/` and compiled into the Claude and Cursor trees by `scripts/sync_skills.py`. **Never hand-edit `.claude/skills/` or `.cursor/skills/`** — they are generated, and CI (`sync_skills.py --check`) rejects any drift.

1. **Create the source.** Add `skills/<skill-name>/SKILL.md` with YAML frontmatter:
   ```yaml
   ---
   name: <skill-name>
   description: >
     What the skill does and the phrases/situations that should trigger it.
     This is what the agent matches on — be specific.
   ---
   ```
   Drop any supporting material (reference docs, templates) in the same folder; it's copied into both generated trees.

2. **(Optional) Platform-specific content.**
   - Add `skills/<skill-name>/claude.md` or `cursor.md` — its contents are appended only to that platform's build; or
   - inline `<!-- claude-only -->…<!-- /claude-only -->` / `<!-- cursor-only -->…<!-- /cursor-only -->` blocks in `SKILL.md`; the markers are stripped from the other platform.

3. **Generate the trees.** Run `python3 scripts/sync_skills.py` (add `--skill <skill-name>` to build just one). This writes `.claude/skills/<skill-name>/` and `.cursor/skills/<skill-name>/`.

4. **Commit canonical + generated together.** Include your `skills/<skill-name>/` source **and** the regenerated `.claude/`/`.cursor/` folders in the same commit, or CI will fail the sync check.

5. **List it** in the [Skills](#skills) table above so people (and agents) can find it.

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

**Failed run** — Paste a pipeline run URL, run UUID, pipeline name, or error snippet. The fix skill parses the input, loads failed task runs, pulls logs and artifacts, classifies the failure, applies remediation, retries when appropriate, and optionally records the fix to your client's memory.

**Author pipeline YAML** — Describe the desired stages/tasks and create a `version: v1` pipeline YAML. The authoring skill validates (via `orchestra-cli` or MCP) and remediates validation errors until clean.

**Review before merge** — Use the triage skill when you want a branch fix, validation run, and triage summary, then explicit approval before merge and production retry.

**Downstream symptom** — Triage can start from a downstream issue (stale dashboard, bad dbt output) and walk upstream through the pipeline graph.

## Contributing

- Edit canonical skills under [`skills/`](skills/) and shared Orchestra material under [`references/orchestra/`](references/orchestra/); do not hand-edit generated trees under `.claude/skills/` or `.cursor/skills/`.
- After changing skills, run `python scripts/sync_skills.py` and commit the regenerated outputs.
- To add a new skill, follow [Adding a skill](#adding-a-skill).
- Recording fixes is optional and deferred to your client's persistent memory — never commit workspace-specific fix history. Extend [`pipeline/diagnosis-patterns.md`](references/orchestra/pipeline/diagnosis-patterns.md) only with generic, reusable patterns.
- Do not commit API keys, `.env` files, or other secrets.

Agents editing this repo should follow [`AGENTS.md`](AGENTS.md).
