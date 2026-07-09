---
name: edit-orchestra-pipeline
description: >
  Create or edit, validate, and remediate Orchestra pipeline YAML files. Use when asked to build a new
  pipeline, add tasks to an existing pipeline, fix pipeline validation errors, or author
  Orchestra workflow definitions from a description. Trigger on phrases like "create a pipeline",
  "add a dbt task", "write orchestra yaml", "fix validate errors", or when editing files under
  orchestra/ or similar pipeline directories.
---

# Create Orchestra Pipeline

Author or update an Orchestra `version: v1` pipeline YAML, validate it, and fix validation errors.

## References and Context
Base information

### Links

- `../../references/orchestra/pipeline/yaml-authoring.md` — schema, integrations, variables, optional sections
- `../../references/orchestra/pipeline/examples.md` — multi-stage patterns (warehouse → LLM → messaging, agents)
- `../../references/orchestra/mcp/tools-quick-ref.md` — `validate_pipeline`, `create_pipeline`, `update_pipeline`
- [Orchestra docs](https://docs.getorchestra.io) for integration parameters not covered in the reference

### Goal

The goal is to accurately create or edit the yml representing a data pipeline in Orchestra, based on the existing pipeline and the user request.

### Additional guidelines

1. Always document in meta
```yml
meta:
  notes: >-
    This is a complex pipeline designed to simulate a bunch of annoying edge
    cases
```
2. Base Pipeline .yml example
```yml
version: v1
name: 'Rivery ingestion to Snowflake dbt #dbt #glue #python #rivery #slack #snowflake
  #metaengine'
pipeline:
  8252937c-272e-440b-bb57-cf5a8df54c11:
    tasks:
      d3491626-3905-411e-b920-3cc5aee745b9:
        integration: DBT_CORE
        integration_job: DBT_CORE_EXECUTE
        parameters:
          commands: dbt ${{ inputs.dbt_command }}
          package_manager: PIP
          python_version: '3.12'
          branch: ${{ inputs.dbt_branch }}
          project_dir: dbt_projects/snowflake
          shallow_clone_dirs: dbt_projects/snowflake
          warehouse_identifier: JH88529.UK-SOUTH.AZURE
          environment_variables: '{
            "DBT_WH":"DBT_WH"
            }'
        depends_on: []
        name: builds analysis models
        connection: dbt_snowflake_blueprints_prod_07025
        operation_metadata:
          94011289-5f33-4aa9-9405-c7fbf8c14fde:
            integration: SNOWFLAKE
            connection: snowflake_tables_24182
        treat_failure_as_warning: true
    depends_on:
    - 3459fb19-f081-43ca-8997-f7f2d54d331d
    name: ''
  3459fb19-f081-43ca-8997-f7f2d54d331d:
    tasks:
      c581252f-2975-4af6-8caf-a42e30527088:
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
          set_outputs: true
          source: GIT
          command: python -m run_dlt_pipelines
          project_dir: python/dlt
          shallow_clone_dirs: python/dlt
        depends_on: []
        name: Execute parallel dlt
        connection: python__production__blueprints__19239
        treat_failure_as_warning: true
    depends_on: []
    name: ''
    matrix:
      inputs:
        gsheets:
        - SHEET_NAME: 1H0UnZ1vJ6WSsZgiVkg96zq52p7qaXkhvodlO1Mzoj6s
          TABLE_NAME: dbt_leads
        - SHEET_NAME: 1TMNhQFZbmaBsa1vIehQzh3vdyfc05damwJ_PIKDF14A
          TABLE_NAME: social_leads
        - SHEET_NAME: 1tImqLq_zLNthL7DDUkTUjU0xHoV_PhdM1zpuJ
          TABLE_NAME: unstructured_feedback
  e6858647-0e86-4530-9eb2-78d080941022:
    tasks:
      08bc69c0-4db0-41cd-8127-9f43fde46cb1:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        parameters:
          statement: Execute task kick_off_task;
        depends_on: []
        name: Execute Task
    depends_on:
    - 3459fb19-f081-43ca-8997-f7f2d54d331d
    - 29750a04-5ce4-41c5-bce0-04e06dbf0ccf
    - 0c3f2c31-e56b-4d2f-8b5f-11d898dc5cff
    name: ''
  29750a04-5ce4-41c5-bce0-04e06dbf0ccf:
    tasks:
      27db9776-b6f1-403a-9e99-12edd814fdc8:
        integration: RIVERY
        integration_job: RIVERY_RUN_RIVER
        parameters:
          river_id: ${{ MATRIX.rivers }}
        depends_on: []
        name: Run Salesforce River
        treat_failure_as_warning: true
    depends_on: []
    condition: ${{ inputs.trigger_name == "sensor" }}
    name: ''
    matrix:
      inputs:
        rivers:
        - some_id
        - some_other_id
  0c3f2c31-e56b-4d2f-8b5f-11d898dc5cff:
    tasks:
      01814a06-c548-4269-b4e9-51dd17615ff2:
        integration: AWS_GLUE
        integration_job: AWS_GLUE_RUN_JOB
        parameters:
          job_name: name
          arguments: '{
            "tables" : "${{ MATRIX.tables }}"
            }'
        depends_on: []
        name: AWS GLUE JOB
    depends_on: []
    name: ''
    matrix:
      inputs:
        tables:
        - table_1
        - table_2
schedule:
- name: Daily at 9am
  cron: 0 9 ? * * *
  timezone: Europe/London
  run_inputs:
    dbt_command: run --select models tag:clean
    dbt_branch: main
    trigger_name: 9am
sensors:
  c767d2c4-9b42-415c-bc81-dcf2f69756d7:
    name: Sensor trigger
    cron: 0 8 ? * * *
    timezone: Europe/London
    timeout_mins: 60
    checks:
      Check to see if snowflake is available:
        integration: SNOWFLAKE
        sensor_type: SNOWFLAKE_QUERY
        parameters:
          query: select * from table where date = current_date() limit 1
        map_outputs:
          sensor_outputs: ${{ outputs.results }}
    run_inputs:
      trigger_name: sensor
webhook:
  enabled: false
configuration:
  concurrency:
    max_active: 10
inputs:
  dbt_command:
    type: string
    default: run --select models tag:clean
  dbt_branch:
    type: string
    default: main
  trigger_name:
    type: string
meta:
  notes: This is a complex pipeline designed for simple demos.
alerts:
- name: Failures
  statuses:
  - FAILED
  destinations:
  - integration: SLACK
    destination: alert-testing
- name: Teams
  statuses:
  - ANY_COMPLETED
  destinations:
  - integration: MICROSOFT_TEAMS
    connection_id: migrated_teams_66347
  - integration: EMAIL
    destination: alerts@getorchestra.io
  custom_message: Custom message
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

## Workflow

### Step 1 — Understand the type of request

Goal: understand if asking to create a pipeline from scratch or if they're editing an existing pipeline, or if they just want conversation.
How: try to fetch the relevant pipeline.yml or pipeline ID. If none exists, then you are doing process A) Create Pipeline. If it does then Process B) edit pipeline.
If neither, and the user wants to converse, exit the skill.

### A PROCESS - CREATING A PIPELINE FROM SCRATCH
Follow this process when no pipeline exists and the user wants to create something from scratch.

### Step 2 A - Create Pipeline; Define goal


From the user message, determine the goal, one of:

- i) Design a high-level example pipeline
- ii) With given connections, actually build a representative pipeline
To decide, GET the relevant integrations and see what is available. If there are < 3 integrations available, choose i). Otherwise, choose ii)
If i), store the integrations. If 0 integrations and if >0 but <3 integrations, store the fivetran, dbt and power bi integrations.
If ii) store the actual integrations to your memory. --> **PIPELINE_GOAL**

### Step 3A) - Gather user requirements

From the user message, determine the request type, one of:
- i) open-ended
- ii) close-ended
For example "Build me a pipeline" Would be i) open-ended. "Built me an ELT pipeline with Fivetran, dbt and power BI" would be close-ended.
Store the request type to memory --> **REQUEST_TYPE**

User the **REQUEST_TYPE** to inform how you design the pipeline. Output the request type to the user.

Draw a mental map of the pipeline. From the user message, determine:

- Purpose, integrations, and data flow
- Target file path (default: `orchestra/<descriptive-name>.yml` in the current repo)
- Connections, schedules, inputs, alerts, or matrix requirements

If no filename is given, derive a short kebab-case name from the pipeline purpose.

Create an example mental map given python, snowflake and sigma inegrations would be a linear pipeline with a python task --> Snowflake query task, e.g. calling a Snowflake Task (capital T) like `execute task snowflake_task` --> Sigma workbook or dataset refresh task --> **MENTAL_PIPELINE_MODEL**

### STEP 4A) Define git status

Using the Orchestra MCP, ascertain if the pipeline is stored in Orchestra or in git.
i) Orchestra
ii) git
Store this value to your memory --> **STORAGE_TYPE**
If stored in Orchestra, create a new version in Orchestra. If stored in git, create a new branch and push changes there.

### Step 5A) - generate .yml

Using the example pipeline in "additional guidelines" and the docs at docs.getorchestra.io, generate the yml. Firsly, define the Task blocks e.g.

```yml
  0c3f2c31-e56b-4d2f-8b5f-11d898dc5cff: // TASK GROUP ID
    tasks:
      01814a06-c548-4269-b4e9-51dd17615ff2: // TASK ID
        integration: AWS_GLUE
        integration_job: AWS_GLUE_RUN_JOB
        parameters:
          job_name: name
          arguments: '{
            "tables" : "${{ MATRIX.tables }}"
            }'
        depends_on: []
        name: AWS GLUE JOB
    depends_on: []
    name: ''
    matrix:
      inputs:
        tables:
        - table_1
        - table_2
```
Then, based on **MENTAL_PIPELINE_MODEL** stitch the ymls together to create the graph, using the dependencies. 
Then, based on the requirements, add additional pipeline-level configurations like
- trigger
- meta
- inputs
- alerts
You should aim to add these wherever possible. If you get stuck, refer to the **How to do certain things** section

### Step 6A) - validate

Run local validation when `orchestra-cli` is available:

```bash
orchestra-cli validate <path/to/pipeline.yml>
```

If only Orchestra MCP is connected, use `validate_pipeline` with the YAML body instead.
If this fails, use the error and save as a new variable **ERROR** and go back to Step 5A) - generate .yml.

### Step 7 — Report

Summarise in a short paragraph or bullet list:

1. File path created or modified
2. Stages and tasks
3. Connections or environment variables to configure in the Orchestra UI
4. Placeholder values the user must replace

Keep the summary concise.

### B PROCESS - EDITING AN EXISTING PIPELINE 
Follow this process when a pipeline exists and the user wants to cedit it

### Step 2B)- Edit Pipeline; Define goal

From the user message, determine the goal, one of:

- i) Write a completely new pipeline, deleting the existing
- ii) Make an amendment to the existing pipeline
Store as **PIPELINE_GOAL** in your memory. IF the PIPELINE_GOAL is new_pipeline, then go to Step 3A), otherwise, noting you must delete the existing yml,  otherwise continue here.

### Step 3B) - Gather user requirements

From the user message, determine the request type, one of:
- i) open-ended
- ii) close-ended
For example "make my pipeline better" Would be i) open-ended. "Add another fivetran task" or "dupliate the dbt task" would be close-ended.
Store the request type to memory --> **REQUEST_TYPE**



### STEP 4B) Define git status

Same as Step 4A)

### Step 5B) - generate .yml

Using the example pipeline in "additional guidelines" and the docs at docs.getorchestra.io, generate the yml changes. Firsly, define the Task blocks to add and to remove or edit e.g.

```yml
  0c3f2c31-e56b-4d2f-8b5f-11d898dc5cff: // TASK GROUP ID
    tasks:
      01814a06-c548-4269-b4e9-51dd17615ff2: // TASK ID
        integration: AWS_GLUE
        integration_job: AWS_GLUE_RUN_JOB
        parameters:
          job_name: name
          arguments: '{
            "tables" : "${{ MATRIX.tables }}"
            }'
        depends_on: []
        name: AWS GLUE JOB
    depends_on: []
    name: ''
    matrix:
      inputs:
        tables:
        - table_1
        - table_2
```
Then, based on **MENTAL_PIPELINE_MODEL** delete, add and edit the existing yml to form a new one, which you will return.
Then, based on the requirements, consider editing the additional pipeline-level configurations like
- trigger
- meta
- inputs
- alerts
If these are already there, do not edit unless instructed. If you get stuck, refer to the **How to do certain things** section

### Step 6B) - validate

Run local validation when `orchestra-cli` is available:

```bash
orchestra-cli validate <path/to/pipeline.yml>
```

If only Orchestra MCP is connected, use `validate_pipeline` with the YAML body instead.
If this fails, use the error and save as a new variable **ERROR** and go back to Step 5B) - generate .yml.

### Step 7 — Report

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
- UUIDS just need to be unique strings, not actual UUIDs, so don't use gross strings for UUIDs
- Don't set inputs on triggers unless asked to. This functionality is for when the user wants to set inputs dynamically or where there are multiple triggers.
## Questions users have
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
Note the depends_on can refer to another task in the group, which will allow you to create very many linear (left to right) repetitions of flows. e.g. Python task --> Snowflake Task --> dbt job, but all parallelised and parameterised. #
You can also check-out the FAQs: https://docs.getorchestra.io/docs/faq
