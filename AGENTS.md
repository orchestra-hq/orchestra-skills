# Agent guide — orchestra-skills

This repository is documentation and workflow instructions for AI agents, not an application runtime. It is distributed as a plugin marketplace: the single `orchestra` plugin bundles every skill, and both Claude Code and Cursor install it from the manifests at the repo root (`.claude-plugin/marketplace.json`, `.cursor-plugin/marketplace.json`). Skills live under `skills/orchestra/skills/` (single source of truth — no generated copies). Shared Orchestra material lives under `skills/orchestra/references/orchestra/`, inside the plugin bundle so a marketplace install carries it along.

## Choose a skill first

| User intent | Skill | Path |
|-------------|-------|------|
| Author a new pipeline YAML | `create-orchestra-pipeline` | `skills/orchestra/skills/create-orchestra-pipeline/SKILL.md` |
| Fix, retry, or explain a failed pipeline without a mandatory merge gate | `fix-orchestra-pipeline` | `skills/orchestra/skills/fix-orchestra-pipeline/SKILL.md` |
| Prepare a fix on a branch, validate, summarize, and stop for approval | `triage-orchestra-pipeline` | `skills/orchestra/skills/triage-orchestra-pipeline/SKILL.md` |
| Downstream symptom with no obvious pipeline error | `triage-orchestra-pipeline` (symptom-first path) | same |
| Set up dbt Slim CI in Orchestra on an existing production pipeline | `orchestra-dbt-slim-ci-setup` | `skills/orchestra/skills/orchestra-dbt-slim-ci-setup/SKILL.md` |

Read the full `SKILL.md` for the matching skill before changing pipelines, opening pull requests, or calling external APIs.

## Reference index

Skill `SKILL.md` files reference shared docs with paths relative to the skill folder (`../../references/orchestra/...`, which resolves to the plugin's `references/orchestra/`). From the repository root, use `skills/orchestra/references/orchestra/`.

| Topic | File |
|-------|------|
| Index | `skills/orchestra/references/orchestra/README.md` |
| YAML authoring schema & validation | `pipeline/yaml-authoring.md` |
| Pipeline pattern examples | `pipeline/examples.md` |
| Failure classification | `pipeline/diagnosis-patterns.md` |
| Remediation actions | `pipeline/remediation-playbooks.md` |
| Past fixes and failure profile | `pipeline/knowledge-store.md` |
| MCP install and config | `mcp/setup.md` |
| MCP tool names and arguments | `mcp/tools-quick-ref.md` |
| Allowed REST read fallback | `api/rest-pipeline-yaml.md` |

## Operating rules

1. **MCP first** — Use Orchestra MCP for listing runs, task runs, logs, artifacts, operations, and retries. Do not call Orchestra REST for those operations.
2. **REST exception** — Read-only `GET /pipelines/{alias_or_id}/yaml` only when MCP cannot return the full pipeline definition; see `api/rest-pipeline-yaml.md`.
3. **Prerequisite** — If Orchestra MCP is not connected, follow `mcp/setup.md` with the user before deep diagnosis.
4. **Parse input early** — Orchestra UI URLs, bare UUIDs, pipeline aliases, pasted errors, and alert text are all valid entry points; the fix skill documents extraction rules.
5. **Evidence before theory** — Prefer `list_task_run_logs`, `download_task_run_log`, artifacts, and `list_operations` over guessing from status fields alone.
6. **Learning is optional** — Recording fixes is deferred to the calling client's persistent memory; never commit workspace-specific fix history. Add only generic, reusable patterns to `pipeline/diagnosis-patterns.md`.
7. **Triage gate** — The triage skill must not merge to the default branch without explicit user approval (`merge`, `yes`, `approve`, and similar).

## Repository layout

```text
.claude-plugin/
  marketplace.json          # Claude Code marketplace → lists the orchestra plugin
.cursor-plugin/
  marketplace.json          # Cursor marketplace → same
skills/
  orchestra/                # the single plugin bundle
    .claude-plugin/plugin.json
    .cursor-plugin/plugin.json
    skills/
      create-orchestra-pipeline/
      fix-orchestra-pipeline/
      triage-orchestra-pipeline/
      orchestra-dbt-slim-ci-setup/
      run-snowflake-quality-tests/
    references/
      orchestra/            # shared docs, bundled with the plugin
        README.md
        pipeline/
        mcp/
        api/
        schemas/
AGENTS.md
README.md
```

## Editing this repository

- Change skill workflows directly in `skills/orchestra/skills/*/SKILL.md` — there is a single skill tree, no generation step. Write skills client-agnostically: describe a capability ("if your client can schedule a wake-up…") rather than naming a specific tool.
- Change shared playbooks and tool notes under `skills/orchestra/references/orchestra/`.
- Adding a skill: create `skills/orchestra/skills/<name>/SKILL.md`; it is exposed automatically by the `orchestra` plugin (no manifest edit needed unless you add a new plugin). Bump the `version` in both `skills/orchestra/.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`.
- Keep user-facing overview in `README.md` and agent routing in this file.
- Never commit secrets or workspace-specific credentials.

## Out of scope

This repo does not ship the Orchestra MCP server implementation, customer pipeline YAML, or integration credentials. Clone [orchestra-mcp](https://github.com/orchestra-hq/orchestra-mcp) and configure MCP separately.
