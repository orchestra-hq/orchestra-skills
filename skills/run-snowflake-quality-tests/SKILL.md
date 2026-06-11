---
name: run-snowflake-quality-tests
description: examine the data we have inside snowflake and based on this, build and deploy a testing pipeline and deploy it to orchestra
---

# Inspect Snowflake

Taking all tables for the database or the # tables from the user, inspect the snowflake using snowflake credentials in the environment.
1. List tables. Identify if table is fact or dimension.
2. For each table, get columns. Identify important columns (e.g. timestamps, IDs, important fields e.g. price, quantity)
3. For each column, identify core tests. Core types:
3a) Completeness: nulls. Assume a reasonable threshold for nulls (e.g. 0% for IDs, 5% for non-key fields)
3b) Freshness: for timestamp columns, check that recent data is present (e.g. within the last day/week). Applies only to Facts
3c) Volume: for facts, identify counts over time to identify anomalies. Choose an appropriate time grain e.g. daily. Choose an appropriate threshold based on the data (e.g. 20% drop MoM)
3d) Sensible values: for things like dates ensure no anomalous values (e.g. year 1900 or 2100). For prices, ensure no negative values.
3e) uniqueness: for dims, check that the key is unique and not null


# Write the Pipeline

A pipeline for a snowflake test in Orchestra looks a bit like this.
```yml
version: v1
name: 'Snowflake Timestamp Data Quality Tests #snowflake #dataquality'
pipeline:
  timestamp_not_null_tests:
    tasks:
      check_timestamp_not_null:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        parameters:
          statement: 'select * from BIGQUERY_SAMPLE.${{ MATRIX.dq_inputs[''schema'']
            }}.${{ MATRIX.dq_inputs[''table''] }}

            where ${{ MATRIX.dq_inputs[''column''] }} is null

            limit 100'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Timestamp Not Null Check
        connection: ${{ ENV.SNOWFLAKE_CONNECTION }}
    depends_on: []
    condition: ${{ task_groups['not_null_tests'].all().status == 'COMPLETED' }}
    name: Timestamp Not Null Tests
    matrix:
      inputs:
        dq_inputs:
        - schema: ORCHESTRA_METADATA
          table: PIPELINE_RUNS
          column: CREATED_AT
        - schema: ORCHESTRA_METADATA
          table: TASK_RUNS
          column: CREATED_AT
        - schema: PUBLIC
          table: ISSUES
          column: CREATED_AT
  timestamp_year_bounds_tests:
    tasks:
      check_timestamp_year_bounds:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        parameters:
          statement: 'select * from BIGQUERY_SAMPLE.${{ MATRIX.dq_inputs[''schema'']
            }}.${{ MATRIX.dq_inputs[''table''] }}

            where year(${{ MATRIX.dq_inputs[''column''] }}) < 2000

            or year(${{ MATRIX.dq_inputs[''column''] }}) > 2030

            limit 100'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Timestamp Anomalous Year Check
        connection: ${{ ENV.SNOWFLAKE_CONNECTION }}
    depends_on:
    - timestamp_not_null_tests
    name: Timestamp Year Bounds Tests
    matrix:
      inputs:
        dq_inputs:
        - schema: ORCHESTRA_METADATA
          table: PIPELINE_RUNS
          column: CREATED_AT
        - schema: ORCHESTRA_METADATA
          table: TASK_RUNS
          column: CREATED_AT
        - schema: PUBLIC
          table: ISSUES
          column: CREATED_AT
schedule:
- name: Daily at 8am
  cron: 0 8 ? * MON-FRI *
  timezone: Europe/London
webhook:
  enabled: false
alerts:
- name: Failures
  statuses:
  - FAILED
  destinations:
  - integration: SLACK
    destination: alert-testing
```
Build the pipeline and ensure all the tests run in groups i.e. this syntax condition: ${{ task_groups['not_null_tests'].all().status == 'COMPLETED' }}.
Ensure an alert is added where appropriate.

# Author the snowflake testing pipeline which is the Orchestra YAML

Create a new branch for the pipeline using the git token, found in the environment variable. Push the yml to the branch. 

### 5. Register the pipeline with Orchestra
Commit the YAML code to the feature branch and push. Then use the
Orchestra MCP `import_pipeline` tool with the YAML contents to register it. The
tool returns the pipeline UUID — save it (you need it for step 7 and for any
future re-runs).

```
mcp__orchestramcp__import_pipeline(yaml="<contents of orchestra/<source>_to_motherduck.yml>")
```

If the pipeline already exists at the same alias, this updates it in place.

###  Trigger on the feature branch and poll
Trigger the pipeline against the branch from step 1, then poll until terminal.

```
mcp__orchestramcp__start_pipeline(alias="<pipeline-uuid>", branch="<feature-branch>")
mcp__orchestramcp__get_pipeline_run_status(pipeline_run_id="<run-uuid>")
```

Poll `get_pipeline_run_status` until the status is not `RUNNING` or `CREATED`.
Report the terminal status and surface the Orchestra UI link:

```
https://app.getorchestra.io/pipeline-runs/<run-uuid>/lineage
```

On failure, call `list_task_runs` (filtered by the run UUID) to find the FAILED
task, then `download_task_run_log` for its log. The most common causes:
- `requirements.txt` missing the new extra (e.g. `dlt[motherduck]`) → the
  `motherduck` destination import errors out. Fix step 4b and retrigger.
- Env var name mismatch between the script and the connection's env config →
  rename in `<source>_pipeline.py` to match the connection. Applies to credential
  vars and `<SOURCE>_MD_STAGING_DATABASE` / `<SOURCE>_MD_PROD_DATABASE` /
  `<SOURCE>_MD_DATASET`.
- API rate-limit / 401 → token is missing from the connection's env config, not
  a code bug.
- Load partially corrupted an existing dataset → `RESTORE` from the snapshot
  created in step 6, then fix the bug and re-run.

Once the run is green on the feature branch, the staging database holds the
fresh load. Prod is still untouched — promote it in step 8.
