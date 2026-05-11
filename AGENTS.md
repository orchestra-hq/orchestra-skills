# Agent guide — orchestra-skills

This repository is documentation and workflow instructions for AI agents, not an application runtime. Skills live under `.claude/skills/`; shared Orchestra material lives under `.claude/references/orchestra/`.

## Choose a skill first

| User intent | Skill | Path |
|-------------|-------|------|
| Fix, retry, or explain a failed pipeline without a mandatory merge gate | `fix-orchestra-pipeline` | `.claude/skills/fix-orchestra-pipeline/SKILL.md` |
| Prepare a fix on a branch, validate, summarize, and stop for approval | `triage-orchestra-pipeline` | `.claude/skills/triage-orchestra-pipeline/SKILL.md` |
| Downstream symptom with no obvious pipeline error | `triage-orchestra-pipeline` (symptom-first path) | same |

Read the full `SKILL.md` for the matching skill before changing pipelines, opening pull requests, or calling external APIs.

## Reference index

From a skill directory, prefix paths with `../../references/orchestra/`. From the repository root, use `.claude/references/orchestra/`.

| Topic | File |
|-------|------|
| Index | `.claude/references/orchestra/README.md` |
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
6. **Learn in-repo** — After a successful fix, append `pipeline/knowledge-store.md`. Add new recurring patterns to `pipeline/diagnosis-patterns.md`. Do not store MCP wiring in the knowledge store.
7. **Triage gate** — The triage skill must not merge to the default branch without explicit user approval (`merge`, `yes`, `approve`, and similar).

## Repository layout

```text
.claude/
  skills/
    fix-orchestra-pipeline/SKILL.md
    triage-orchestra-pipeline/SKILL.md
  references/
    orchestra/
      README.md
      pipeline/
      mcp/
      api/
AGENTS.md
README.md
```

## Editing this repository

- Change skill workflows in `.claude/skills/*/SKILL.md`.
- Change shared playbooks and tool notes under `.claude/references/orchestra/`.
- Keep user-facing overview in `README.md` and agent routing in this file.
- Never commit secrets or workspace-specific credentials.

## Out of scope

This repo does not ship the Orchestra MCP server implementation, customer pipeline YAML, or integration credentials. Clone [orchestra-mcp](https://github.com/orchestra-hq/orchestra-mcp) and configure MCP separately.
