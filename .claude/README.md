# Claude layout

| Directory | Role |
|-----------|------|
| [`skills/`](skills/) | Generated Claude Code skills (`SKILL.md` per folder) |
| [`references/`](references/) | Pointer to shared Orchestra references at repo root |

Human-oriented setup and skill summaries: [`../README.md`](../README.md). Agent routing and operating rules: [`../AGENTS.md`](../AGENTS.md).

Author skills under [`../skills/`](../skills/) and run `python scripts/sync_skills.py` to refresh this tree. Generated skills reference shared docs with paths relative to the skill folder, for example `../../../references/orchestra/mcp/tools-quick-ref.md`.
