# Orchestra pipeline YAML authoring

Schema reference for creating and editing Orchestra pipeline definitions (`version: v1`).
Use with the `create-orchestra-pipeline` skill and `orchestra-cli validate`.

Official docs: [docs.getorchestra.io](https://docs.getorchestra.io).

## File layout

- Default directory in Git-backed repos: `orchestra/<descriptive-name>.yml`
- If the repo uses another convention (`pipelines/`, `.orchestra/`), match existing files
- Derive a short kebab-case filename from the pipeline purpose when the user does not specify one

Before writing, list existing pipeline YAML in the repo and read one or two files that use
similar integrations (task group IDs, connection naming, schedules).

## Document structure

```yaml
version: v1
name: '<descriptive name> #tag1 #tag2'
pipeline:
  <task_group_id>:           # descriptive name or uuid4
    tasks:
      <task_id>:             # descriptive name or uuid4
        integration: <INTEGRATION>
        integration_job: <JOB_TYPE>
        parameters:
          # integration-specific params
        depends_on: []       # other task IDs within this group
        name: <Human readable task name>
        # tags: omit entirely if no tags — do NOT include tags: []
        connection: <connection_id or ${{ ENV.VAR }}>  # omit if not needed
    depends_on: []           # list of task_group_ids this group waits for
    name: '<Stage Name>'
```

### Required fields

- `version: v1`
- `name:` — include `#tags` for discoverability when useful
- Each task: `integration`, `integration_job`, `parameters`, `depends_on`, `name`
- Omit `tags` when unused — never write `tags: []`

## Integration reference

| Integration | integration_job | Key parameters |
|---|---|---|
| FIVETRAN | FIVETRAN_SYNC_ALL | `connector_id` |
| DBT_CORE | DBT_CORE_EXECUTE | `commands`, `package_manager` (PIP\|UV), `python_version`, `project_dir`, `shallow_clone_dirs` |
| PYTHON | PYTHON_EXECUTE_SCRIPT | `command`, `package_manager`, `python_version`, `build_command`, `source: GIT`, `project_dir`, `environment_variables`, `set_outputs` |
| SNOWFLAKE | SNOWFLAKE_RUN_QUERY | `statement`, `role`, `database`, `schema` |
| SNOWFLAKE | SNOWFLAKE_RUN_TEST | `statement`, `error_threshold_expression`, `warn_threshold_expression` |
| GCP_BIG_QUERY | GCP_BQ_RUN_QUERY_JOB | `query` |
| GCP_CLOUD_RUN | GCP_CLOUD_RUN_EXECUTE_JOB | `job_name` |
| TABLEAU_CLOUD | TABLEAU_REFRESH_EXTRACT | `project_name`, `datasource_name` |
| POWER_BI | POWER_BI_REFRESH_DATASET | `dataset_id` |
| HTTP | HTTP_REQUEST | `path`, `method`, `body`, `custom_headers` |
| ORCHESTRA | APPROVAL | `message_integration`, `message_connection_id`, `message_destination` |
| OPEN_AI | OPEN_AI_CHAT | `prompt`, `model`, `context`, `instructions`, `set_outputs` |
| AWS_LAMBDA | AWS_LAMBDA_EXECUTE_ASYNC_FUNCTION | `function_name` |
| ESTUARY | ESTUARY_CHECK_FLOW | `task`, `error_threshold`, `warn_threshold` |
| LIGHTDASH | LIGHTDASH_REFRESH_DASHBOARD | `dashboard_id`, `invalidate_cache` |

## Connection format

```yaml
connection: my_snowflake_12345   # descriptive-name_XXXXX — 5-digit suffix assigned by Orchestra
connection: ${{ ENV.SNOWFLAKE_CONNECTION_NAME }}   # environment-specific, set per Environment in the UI
connection: null                 # no distinct connection needed — Orchestra uses the workspace default
```

`null` is valid and often preferable when nothing in the source distinguishes a specific
credential — never invent a placeholder suffix or a fake `${{ ENV.VAR }}` just to fill the field.
The same rule applies to any parameter that duplicates connection-level scope (e.g. a Power BI
`workspace_id`): leave it unset and let the connection's own configured value apply unless a task
genuinely needs to override it. If a required value truly can't be determined statically (an ID
only resolvable by calling a live API), use a placeholder and flag it with a `# MANUAL:` comment
rather than shipping a fabricated literal or GUID.

## Optional `configuration:` block (retries/timeout/concurrency)

```yaml
configuration:          # pipeline-level default; a task's own configuration: overrides it
  retries: 2             # integer
  retry_delay: 5         # integer MINUTES — not seconds, not a timedelta string. Max 120
  timeout: 3600           # integer seconds
  concurrency:
    max_active: 1          # integer >= 0; null/omit = no limit
```

`retry_delay` is minutes despite sources like Dagster/Airflow/Prefect typically expressing retry
delay in seconds — convert and round up, and clamp to 120 if the source value is larger.

## Variable syntax

- Environment / connection refs: `${{ ENV.VAR_NAME }}`
- Pipeline inputs: `${{ inputs.param_name }}`
- Matrix vars: `${{ MATRIX.key }}`
- Orchestra system: `${{ ORCHESTRA.TASK_RUN_ID }}`, `${{ ORCHESTRA.CURRENT_TIME }}`
- Task outputs: `${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-name'].OUTPUTS['results'] }}`

## Optional top-level sections

**Schedule (six-field cron, minute-first — not standard seconds-first Quartz):**
`minute hour day-of-month month day-of-week [year]`, e.g. `0 8 ? * * *` = 8:00am daily. Confirmed
empirically against `validate_pipeline` — an out-of-range value in field 1 errors as "Invalid
minute value," field 2 as "Invalid hour value," not seconds/minutes as a literal Quartz reading
would suggest.

```yaml
schedule:
- name: Daily 8am
  cron: 0 8 ? * * *
  timezone: UTC
  environment: null
  branch: null
```

**Inputs:**

```yaml
inputs:
  param_name:
    type: string
    default: 'default value'
```

**Webhook:**

```yaml
webhook:
  enabled: false
```

**Alerts:**

```yaml
alerts:
- name: On Failure
  statuses: [FAILED, RUNNING_TIMEOUT]
  destinations:
  - integration: SLACK
    destination: '#data-alerts'
```

**Matrix (parallel tasks):**

```yaml
matrix:
  inputs:
    connectors:
    - conn_1
    - conn_2
```

Reference matrix values in task parameters as `${{ MATRIX.connectors }}`. Matrix tasks run in
parallel by default; add `sequential: true` under `matrix` to run them one after another instead
(e.g. to chain repeated linear flows without hand-writing a task per repetition).

## Validation

After writing or editing a file:

```bash
orchestra-cli validate <path/to/pipeline.yml>
```

Prefer MCP `validate_pipeline` when the Orchestra MCP server is connected and you need to
validate without a local CLI install.

### Common validation errors

| Error type | Fix |
|---|---|
| Missing required field | Add the field with a sensible value or placeholder |
| Invalid integration name | Correct spelling (all caps); see integration table |
| Invalid job type | Match `integration_job` to the integration |
| Unknown parameter | Remove or rename to match the integration schema |
| Invalid `depends_on` reference | Referenced ID must exist at the correct level (task vs task group) |
| YAML syntax error | Fix indentation, quoting, or structure |
| Invalid cron expression | Six fields, minute-first: `0 8 ? * * *` (not seconds-first Quartz) |
| `tags` on a task group (`extra_forbidden`) | `TaskGroupModel` has no `tags` field — confirmed live against `/pipelines/schema`. Put `tags:` on each task, never on the stage wrapping it |
| Invalid threshold expression (e.g. on `SNOWFLAKE_RUN_TEST`) | `error_threshold_expression` / `warn_threshold_expression` need a single-character comparator (`=`, `>`, `<`, `>=`, `<=`, `!=`) + a non-negative integer — confirmed live: `'== 0'` is rejected, `'= 0'` is accepted. Python-style `==` doesn't work here |

Re-run validation after each fix. Cap remediation at around 5 attempts — patch only what the
latest errors report rather than regenerating from scratch each time; if still failing after 5,
present the YAML with the remaining errors listed instead of continuing indefinitely.

### Runtime substitution gotcha

`${{ ... }}` substitutions (`${{ inputs.x }}`, `${{ ORCHESTRA.PIPELINE_RUN_TASKS[...].OUTPUTS[...] }}`)
are inserted as raw text with no escaping for whatever syntax surrounds them. A JSON-shaped output
substituted into a quoted string breaks on the first internal `"`. When a substituted value could
itself contain the quote character wrapping it (JSON-shaped values are the common case), wrap it in
Python triple-quotes instead — `json.loads("""${{ ... }}""")` — rather than single/double quotes.
There's no triple-quote equivalent for JSON-typed parameters like `environment_variables`; avoid
routing a quote-containing value through those, and substitute it directly in a `code:`/`command:`
block instead.

## User handoff

Report: file path, stage → task structure, connections or env vars to configure in the
Orchestra UI, and any placeholder values (for example `your_connector_id`) still to replace.
