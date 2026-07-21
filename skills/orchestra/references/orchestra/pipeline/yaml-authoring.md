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

## Variable syntax

- Environment / connection refs: `${{ ENV.VAR_NAME }}`
- Pipeline inputs: `${{ inputs.param_name }}`
- Matrix vars: `${{ MATRIX.key }}`
- Orchestra system: `${{ ORCHESTRA.TASK_RUN_ID }}`, `${{ ORCHESTRA.CURRENT_TIME }}`
- Task outputs: `${{ ORCHESTRA.PIPELINE_RUN_TASKS['task-name'].OUTPUTS['results'] }}`

## Optional top-level sections

**Schedule (Quartz cron — six fields):**

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
| Invalid cron expression | Quartz format: `0 8 ? * * *` (six fields, not five) |

Re-run validation after each fix until the output is clean.

## User handoff

Report: file path, stage → task structure, connections or env vars to configure in the
Orchestra UI, and any placeholder values (for example `your_connector_id`) still to replace.
