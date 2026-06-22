---
name: create-orchestra-pipeline-v2
description: >
  Create, validate, and remediate Orchestra pipeline YAML files. Use when asked to build a new
  pipeline, add tasks to an existing pipeline, fix pipeline validation errors, or author
  Orchestra workflow definitions from a description. Trigger on phrases like "create a pipeline",
  "add a dbt task", "write orchestra yaml", "fix validate errors", or when editing files under
  orchestra/ or similar pipeline directories.
disable-model-invocation: true
---

# Create Orchestra Pipeline

Author or update an Orchestra `version: v1` pipeline YAML, validate it, and fix validation errors.

## References

- `../../../references/orchestra/pipeline/yaml-authoring.md` — schema, integrations, variables, optional sections
- `../../../references/orchestra/pipeline/examples.md` — multi-stage patterns (warehouse → LLM → messaging, agents)
- `../../../references/orchestra/mcp/tools-quick-ref.md` — `validate_pipeline`, `create_pipeline`, `update_pipeline`
- [Orchestra docs](https://docs.getorchestra.io) for integration parameters not covered in the reference

## Context

Identify what the person is trying to automate
1. Data Pipeline end to end
2. Data Pipeline (partial)
3. Automation pipeline (event-driven or for a random automation)

If 1: e2e data pipeline typically an extract, intermediate load (e.g. S3 to Snowflake via Snowflake Task), Transformation (e.g. Snowflake Tasks, stored Procs, dbt cloud or core), and then activation e.g. BI process. Typically linear.

If 2. It may be a subset of the below. It is more likely to have a pipeline or sensor trigger.

If 3. It likely has a webhook trigger and then passes an input through a linear flow, like n8n or zapier.

### Additional things.

1. Always document in meta
```yml
meta:
  notes: >-
    This is a complex pipeline designed to simulate  abunch of annoying edge
    cases
```

### How to do certain things

- Triggers: https://docs.getorchestra.io/docs/core-concepts/triggers. Preference for cron and webhook where possible.
- Sensor: https://docs.getorchestra.io/docs/core-concepts/triggers/sensors. Set the sensor outputs using a new input `sensor_event` and relevant values. Add the input to downstream tasks where appropriate
- Inputs: where possible, parameterise any branch, command and other helpful parameters
- Connections: do not add connection strings when you generate the .yml; lacking a connection_id, Orchestra picks a default
- Environments: where an environment variable exists, use this for the connection string always https://docs.getorchestra.io/docs/core-concepts/environments
- Alerts: add alerts for failures as a matter of course, using the relevant alerting config. 
```yml
    alerts:
      - name: Failures
        statuses:
          - FAILED
        destinations:
          - integration: SLACK
            destination: alerts-data
            connection_id: default_00000 <-- should specify in alerts
```
- Conditionals: reference the documentation. Conditionals are hard. 
- Matrices definition: best thing to do is to define the matrix in code and then reference it in the task. 
```yml
      38e0b377-da9e-42bc-af8f-38708407ab57:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          environment_variables: '{
            "SHEET_NAME": "${{ MATRIX.gsheets[''SHEET_NAME''] }}",
            "TABLE_NAME":"${{ MATRIX.gsheets[''TABLE_NAME''] }}"
            }'
          set_outputs: false
          source: GIT
          command: python -m run_dlt_pipelines
          branch: ${{ inputs.python_branch }}
          project_dir: python/dlt
          shallow_clone_dirs: python/dlt
        depends_on: []
        name: Some arbitrary python
        matrix:
          inputs:
            gsheets:
            - SHEET_NAME: 1H0UnZ1vJ6WSsZgiVkg96zq52p7qaXkhvodlO1Mzoj6s
              TABLE_NAME: dbt_leads
            - SHEET_NAME: 1TMNhQFZbmaBsa1vIehQzh3vdyfc05damwJ_PIKDF14A
              TABLE_NAME: social_leads
            - SHEET_NAME: 1tImqLq_zLNthL7DDUkTUjU0xHoV_PhdM1zpuJ
              TABLE_NAME: unstructured_feedback
```

### Random questions people have

- How to skip a specific task on a specific day. In a flow A-- > B --> C you basically need to create an input which gets set as the value of  `true` on the day or time it should run. https://docs.getorchestra.io/docs/core-concepts/variables. The task C needs to run whenever B is `SUCEEDED` or `SKIPPED` because otherwise C won't run if B gets skipped.
- How to create a horizontal or sequential list of tasks using Matrices? 
This yml has two tasks which will run in parallel, with the matrix applying to each.
```yml
      38e0b377-da9e-42bc-af8f-38708407ab57:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          package_manager: PIP
          python_version: '3.12'
          build_command: pip install -r requirements.txt
          environment_variables: '{

            "SHEET_NAME": "${{ MATRIX.gsheets[''SHEET_NAME''] }}",


            "TABLE_NAME":"${{ MATRIX.gsheets[''TABLE_NAME''] }}"


            }'
          set_outputs: false
          source: GIT
          command: python -m run_dlt_pipelines
          branch: ${{ inputs.python_branch }}
          project_dir: python/dlt
          shallow_clone_dirs: python/dlt
        depends_on: []
        name: Some arbitrary python
      cc7e6c6f-6ce4-4679-b135-e8be243c209f:
        integration: ORCHESTRA
        integration_job: APPROVAL
        parameters: {}
        depends_on: []
        name: group
    depends_on: []
    name: group
    matrix:
      inputs:
        gsheets:
        - SHEET_NAME: 1H0UnZ1vJ6WSsZgiVkg96zq52p7qaXkhvodlO1Mzoj6s
          TABLE_NAME: dbt_leads
        - SHEET_NAME: 1TMNhQFZbmaBsa1vIehQzh3vdyfc05damwJ_PIKDF14A
          TABLE_NAME: social_leads
        - SHEET_NAME: 1tImqLq_zLNthL7DDUkTUjU0xHoV_PhdM1zpuJ
          TABLE_NAME: unstructured_feedback
      sequential: true
```
Note the depends_on can refer to another task in the group, which will allow you to create very many linear (left to right) repetitions of flows. e.g. Python task --> Snowflake Task --> dbt job, but all parallelised and parameterised. 

## Workflow

### Step 1 — Understand the request

From the user message, determine:

- Purpose, integrations, and data flow
- Target file path (default: `orchestra/<descriptive-name>.yml` in the current repo)
- Connections, schedules, inputs, alerts, or matrix requirements
- GET INtegrations!!! Someone is unlikely to ask you to make a pipeline with integrations they don't have
If no filename is given, derive a short kebab-case name from the pipeline purpose.

### Step 2 — Match repo conventions

List existing pipeline YAML (typically `orchestra/`, or paths the user names). Read one or two
pipelines that use similar integrations before writing — match task group and task ID style,
connection references, and schedule format.

### Step 3 — Write or edit the YAML

Follow `../../../references/orchestra/pipeline/yaml-authoring.md` for structure, required fields,
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
