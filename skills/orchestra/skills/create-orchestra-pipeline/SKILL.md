---
name: create-orchestra-pipeline
description: >
  Create, validate, and remediate Orchestra pipeline definitions, as YAML or OML. Use when asked
  to build a new pipeline, add tasks to an existing pipeline, fix pipeline validation errors, or
  author Orchestra workflow definitions from a description. Trigger on phrases like "create a
  pipeline", "add a dbt task", "write orchestra yaml", "write orchestra oml", "fix validate
  errors", or when editing `.yml`, `.yaml` or `.oml` files under orchestra/ or similar pipeline
  directories.
---

# Create Orchestra Pipeline

Author or update an Orchestra `version: v1` pipeline definition — YAML or
[OML](https://docs.getorchestra.io/docs/core-concepts/pipelines/oml) — validate it, and fix
validation errors.

## References

- `../../references/orchestra/pipeline/yaml-authoring.md` — schema, integrations, variables, optional sections
- `../../references/orchestra/pipeline/examples.md` — multi-stage patterns (warehouse → LLM → messaging, agents)
- `../../references/orchestra/mcp/tools-quick-ref.md` — `validate_pipeline`, `create_pipeline`, `update_pipeline`
- [Orchestra docs](https://docs.getorchestra.io) for integration parameters not covered in the reference

## Workflow

### Step 1 — Understand the request

From the user message, determine:

- Purpose, integrations, and data flow
- Target file path (default: `orchestra/<descriptive-name>.yml` in the current repo); write
  `.oml` instead when the user asks for OML or the repo already uses it
- Connections, schedules, inputs, alerts, matrix, or anomaly detection requirements

If no filename is given, derive a short kebab-case name from the pipeline purpose.

When editing an existing pipeline, read the deployed one before changing it —
`pipeline_context(<alias>)` returns its full definition alongside its metadata, so there
is no guessing at the YAML structure it already uses. Check whether it's Git-backed or
Orchestra-backed before deciding how to apply the change; that metadata includes
`storageProvider`. For Git-backed pipelines, edit the repo YAML directly (the repo is
the source of truth, so read the deployed definition for context only); `update_pipeline`
cannot write to them. For Orchestra-backed pipelines with no local YAML, use the MCP
tools instead of authoring a file.

### Step 2 — Match repo conventions

List existing pipeline definitions (typically `orchestra/`, or paths the user names). Read one or two
pipelines that use similar integrations before writing — match task group and task ID style,
connection references, and schedule format.

### Step 3 — Write or edit the definition

Follow `../../references/orchestra/pipeline/yaml-authoring.md` for structure, required fields,
integration table, and variable syntax. The same model applies to `.oml`; that reference's OML
section covers the syntax and quoting differences. Omit empty `tags` arrays.

Editorial defaults, unless the user asks otherwise:

- Prefer `cron` or `webhook` triggers over sensors where the source integration supports it.
- Don't hardcode a `connection`; omit it and let Orchestra pick the default, or reference an
  existing environment variable (`${{ ENV.VAR }}`) when one already covers that connection.
- Add a failure alert as a matter of course — most pipelines should have one.
- For matrices, define the `inputs` list once on the task group, then reference values in task
  parameters as `${{ MATRIX.key }}` rather than repeating the list per task.
- Only add an `anomalies` block when the user asks for duration/anomaly monitoring — unlike
  alerts, it isn't a default addition. It's also a poor fit for short or infrequently-run tasks;
  say so rather than adding it if the pipeline doesn't suit it.

### Step 4 — Validate

Pick the tool that matches the file's extension. For `.yml` / `.yaml`, run local validation when
`orchestra-cli` is available:

```bash
orchestra-cli validate <path/to/pipeline.yml>
```

For `.oml`, validate with the `orchestra-lang` package (`pip install orchestra-lang`, then report
each entry of `oml_lang.analyze(source).errors()` with its line and column). `orchestra-cli
validate` reads its input as YAML, so it can't parse an `.oml` file — see the OML section of
`yaml-authoring.md`.

If only Orchestra MCP is connected, use `validate_pipeline` with the definition body instead
(converted to JSON with `oml_lang.to_json` for `.oml`).

### Step 5 — Remediate errors

For each validation error, apply the fixes in the table in `yaml-authoring.md`. Re-validate,
patching only what the latest errors report. Cap this at around 5 attempts — if still failing,
present the YAML with the remaining errors listed rather than continuing indefinitely.

### Step 5.5 — Confirm before deploying yourself

If this skill is calling `create_pipeline`/`update_pipeline` directly (not just writing/validating
the file for the user to deploy themselves), confirm two things first rather than shipping
placeholders: every non-null `connection:` value matches a real connection in the account (list
via MCP `list_integration_connections` and suggest a best match by integration type), and
`parameters.project_dir` on every `DBT_CORE` task if the dbt project might not be at the repo root.

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
  automatically on `*.yml` / `*.yaml` — still run validation explicitly when unsure. Those hooks
  don't match `.oml`, so always validate OML yourself.
- For Git-backed pipelines, committing YAML does not deploy until the repo is connected in
  Orchestra; call out any UI setup the user still needs.
- Task group and task IDs only need to be unique strings, not real UUIDs.
- Don't add `run_inputs` to a trigger unless asked — that's for setting inputs dynamically per
  trigger, not a default every pipeline needs.
