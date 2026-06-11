# Plan: migrate to the plugin-marketplace layout

**Audience:** an agent (or engineer) implementing this in a follow-up PR.
**Goal:** distribute the skills to Claude Code **and** Cursor through the supported
plugin-marketplace mechanism, so a single `skills/` source serves both clients with **no
generated `.claude/skills/` or `.cursor/skills/` copies** and no sync script.

This is the model used by [`dbt-labs/dbt-agent-skills`](https://github.com/dbt-labs/dbt-agent-skills):
one source tree, exposed via small manifest files; both editors read the same files.

## Current state (after the generation-removal PR)

- Skills live once under `skills/<skill-name>/SKILL.md` (+ each skill's own `references/`/`templates/`).
- No generated trees, no `scripts/sync_skills.py`, no `Skills sync` CI. The `Validate Skills`
  workflow still lints each `skills/*/SKILL.md` (frontmatter + ≤500 lines).
- Skills are **not** currently auto-discovered by Claude Code/Cursor (that's what this migration restores).

## Target layout

```text
.claude-plugin/
  marketplace.json          # lists plugins; points at ./skills/<plugin>
.cursor-plugin/
  marketplace.json          # same, for Cursor (list the plugins Cursor should expose)
skills/
  orchestra/                # one plugin bundle (name TBD — see decisions)
    .claude-plugin/plugin.json
    .cursor-plugin/plugin.json
    skills/
      create-orchestra-pipeline/SKILL.md
      fix-orchestra-pipeline/SKILL.md
      triage-orchestra-pipeline/SKILL.md
      orchestra-dbt-slim-ci-setup/SKILL.md
      run-snowflake-quality-tests/SKILL.md
references/orchestra/        # shared docs (unchanged)
```

Reference: dbt's root manifest lists plugins with `"source": "./skills/<plugin>"`; each plugin
dir holds `.claude-plugin/plugin.json` and a `skills/` subfolder. Confirm exact `plugin.json` /
`marketplace.json` fields against the current Claude Code marketplace schema
(`https://anthropic.com/claude-code/marketplace.schema.json`) before writing them.

## Steps

1. **Decide plugin grouping** (see decisions below). Simplest: one plugin, `orchestra`,
   containing all five skills.
2. **Move skills** from `skills/<name>/` to `skills/orchestra/skills/<name>/` (keep each
   skill's own `references/`/`templates/` with it). `git mv` to preserve history.
3. **Fix relative reference paths.** Skills currently link to shared docs via
   `../../references/orchestra/...`. After the move they sit one level deeper
   (`skills/orchestra/skills/<name>/`), so audit and update those links (likely
   `../../../../references/orchestra/...`), **or** decide whether shared docs should be
   vendored per-plugin instead. Grep: `grep -rn "references/orchestra" skills/`.
4. **Write the manifests:**
   - `skills/orchestra/.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json`
     (name, description, version).
   - Root `.claude-plugin/marketplace.json` and `.cursor-plugin/marketplace.json`
     (marketplace name, owner, `plugins[].source: "./skills/orchestra"`).
5. **Update CI.** Point `Validate Skills` at the new path
   (`skills/*/skills/*/SKILL.md`). Optionally add a check that every skill is listed in a
   plugin and the manifests are valid JSON against the schema.
6. **Update docs.** README "What is in this repo", Install (replace the interim
   "symlink into `.claude/skills/`" note with real install: add the marketplace, install the
   plugin), and AGENTS.md layout + skill paths. Delete this plan file or mark it done.
7. **Verify discovery** in both Claude Code and Cursor: add the marketplace, install the
   plugin, confirm each skill triggers.

## Decisions to confirm before starting

- **Does Cursor consume `.cursor-plugin/marketplace.json`?** dbt-labs ships one, so almost
  certainly yes — but verify against current Cursor docs, and decide which skills Cursor
  should expose (dbt-labs exposes a subset in their Cursor marketplace).
- **One plugin or several?** dbt-labs split into `dbt`, `dbt-migration`, `dbt-extras`. One
  `orchestra` plugin is fine to start; split later if the catalogue grows.
- **Plugin name & versioning.** Pick a stable plugin name and a version scheme (dbt-labs uses
  changie-managed changelogs; not required for v1).
- **Shared references:** link via relative paths (one source) vs. vendor a copy into the
  plugin (self-contained). Prefer linking unless the marketplace install doesn't carry
  sibling `references/` along.
