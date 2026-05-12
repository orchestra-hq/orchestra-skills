---
name: create-orchestra-pipeline
description: >
  Create, validate, and remediate Orchestra pipeline YAML files. Use when asked to build a new
  pipeline, add tasks to an existing pipeline, fix pipeline validation errors, or author
  Orchestra workflow definitions from a description. Trigger on phrases like "create a pipeline",
  "add a dbt task", "write orchestra yaml", "fix validate errors", or when editing files under
  orchestra/ or similar pipeline directories.
---

# Create Orchestra Pipeline

Author or update an Orchestra `version: v1` pipeline YAML, validate it, and fix validation errors.

## References

- `../../references/orchestra/pipeline/yaml-authoring.md` — schema, integrations, variables, optional sections
- `../../references/orchestra/pipeline/examples.md` — multi-stage patterns (warehouse → LLM → messaging, agents)
- `../../references/orchestra/mcp/tools-quick-ref.md` — `validate_pipeline`, `create_pipeline`, `update_pipeline`
- [Orchestra docs](https://docs.getorchestra.io) for integration parameters not covered in the reference

## Workflow

### Step 1 — Understand the request

From the user message, determine:

- Purpose, integrations, and data flow
- Target file path (default: `orchestra/<descriptive-name>.yml` in the current repo)
- Connections, schedules, inputs, alerts, or matrix requirements

If no filename is given, derive a short kebab-case name from the pipeline purpose.

### Step 2 — Match repo conventions

List existing pipeline YAML (typically `orchestra/`, or paths the user names). Read one or two
pipelines that use similar integrations before writing — match task group and task ID style,
connection references, and schedule format.

### Step 3 — Write or edit the YAML

Follow `../../references/orchestra/pipeline/yaml-authoring.md` for structure, required fields,
integration table, and variable syntax. Omit empty `tags` arrays.

### Step 4 — Validate

Run local validation when `orchestra-cli` is available:

```bash
orchestra-cli validate <path/to/pipeline.yml>
```

If only Orchestra MCP is connected, use `validate_pipeline` with the YAML body instead.

### Step 5 — Remediate errors

For each validation error, apply the fixes in the table in `yaml-authoring.md`. Re-validate
until clean.

### Step 6 — Report

Summarise in a short paragraph or bullet list:

1. File path created or modified
2. Stages and tasks
3. Connections or environment variables to configure in the Orchestra UI
4. Placeholder values the user must replace

Keep the summary concise.

## Notes

- Pipelines can represent both data workflows and AI agent workflows; use `PYTHON` /
  `PYTHON_EXECUTE_SCRIPT` with `build_command` and `project_dir` for in-repo agent entrypoints.
- After saving YAML in repos that use Cursor hooks, `orchestra-cli validate` may run
  automatically on `*.yml` / `*.yaml` — still run validation explicitly when unsure.
- For Git-backed pipelines, committing YAML does not deploy until the repo is connected in
  Orchestra; call out any UI setup the user still needs.
