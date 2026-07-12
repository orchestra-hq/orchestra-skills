---
name: run-snowflake-quality-tests
description: Examines Snowflake data sources, infers appropriate data quality tests, builds a structured Orchestra YAML testing pipeline, and deploys and triggers it via Orchestra MCP tools. Use when the user asks about Snowflake data validation, data quality testing, pipeline deployment to Orchestra, orchestration of test workflows, data warehouse quality checks, or running Snowflake tests against fact and dimension tables.
---

# Step 1: Inspect Snowflake

Taking all tables for the database or the specific tables from the user, inspect Snowflake using Snowflake credentials in the environment.

1. **List tables** — identify whether each table is a fact or dimension.
2. **Get columns** — for each table, retrieve column names and types. Identify important columns (e.g. timestamps, IDs, key fields like price or quantity).
3. **Identify core tests per column:**
   - **3a) Completeness:** Null rate — 0% for IDs, 5% threshold for non-key fields.
   - **3b) Freshness:** Timestamp columns on fact tables — within last day or week.
   - **3c) Volume:** Row counts over time on facts — 20% drop MoM threshold.
   - **3d) Sensible values:** Dates outside 2000–2030; negative prices.
   - **3e) Uniqueness:** Primary key on dimensions — unique and not null.

Use `INFORMATION_SCHEMA` queries to enumerate tables and columns:
```sql
-- List all tables in a schema
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
FROM <DATABASE>.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = '<SCHEMA>';

-- Get columns for a table
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM <DATABASE>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<SCHEMA>' AND TABLE_NAME = '<TABLE>'
ORDER BY ORDINAL_POSITION;

-- Sample row count and null rate for a column
SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN <COLUMN> IS NULL THEN 1 ELSE 0 END) AS null_count,
  ROUND(100.0 * SUM(CASE WHEN <COLUMN> IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS null_pct
FROM <DATABASE>.<SCHEMA>.<TABLE>;
```

Make strong assertions about the tests you propose, then prompt the user to validate them before proceeding.

# Step 2: Write the Pipeline

Build the Orchestra YAML pipeline ensuring:
- Tests are organised into logical groups, one per test category.
- Groups are sequenced via `depends_on` (a group only starts once the groups it lists have completed) — never gate a group on its own status.
- An alert block is included for failures.
- The `connection` field references: `${{ ENV.SNOWFLAKE_CONNECTION }}`.

The pattern for each task group is shown below. Extend it for every test category identified in Step 1, chaining groups via `depends_on`.

```yml
version: v1
name: 'Snowflake Data Quality Tests #snowflake #dataquality'
pipeline:
  not_null_tests:
    tasks:
      check_not_null:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        parameters:
          statement: 'select * from <DATABASE>.${{ MATRIX.dq_inputs[''schema''] }}
            .${{ MATRIX.dq_inputs[''table''] }}
            where ${{ MATRIX.dq_inputs[''column''] }} is null
            limit 100'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Not Null Check
        connection: ${{ ENV.SNOWFLAKE_CONNECTION }}
    depends_on: []
    name: Not Null Tests
    matrix:
      inputs:
        dq_inputs:
        - schema: <SCHEMA>
          table: <TABLE>
          column: <COLUMN>
  year_bounds_tests:
    tasks:
      check_year_bounds:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_TEST
        parameters:
          statement: 'select * from <DATABASE>.${{ MATRIX.dq_inputs[''schema''] }}
            .${{ MATRIX.dq_inputs[''table''] }}
            where year(${{ MATRIX.dq_inputs[''column''] }}) < 2000
            or year(${{ MATRIX.dq_inputs[''column''] }}) > 2030
            limit 100'
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: Anomalous Year Check
        connection: ${{ ENV.SNOWFLAKE_CONNECTION }}
    depends_on:
    - not_null_tests
    name: Year Bounds Tests
    matrix:
      inputs:
        dq_inputs:
        - schema: <SCHEMA>
          table: <TABLE>
          column: <COLUMN>
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

**Validation checkpoint:** Validate the generated YAML (check syntax, verify test coverage matches Step 1 findings) and confirm the proposed test scope with the user before proceeding.

# Step 3: Author the Snowflake Testing Pipeline YAML

Create a new feature branch using the Git token found in the environment variables. Push the generated `.yml` file to that branch.

1. Use the Git token from the environment to authenticate.
2. Create a new branch (e.g. `feature/snowflake-dq-tests`).
3. Write the pipeline YAML to a file (e.g. `orchestra/snowflake_dq_tests.yml`).
4. Commit and push the file to the feature branch.

### Step 4: Register the Pipeline with Orchestra

Use the Orchestra MCP `import_pipeline` tool with the YAML contents to register it. The tool returns the pipeline UUID — save it (needed for Step 5).

```
mcp__orchestramcp__import_pipeline(yaml="<contents of orchestra/snowflake_dq_tests.yml>")
```

If the pipeline already exists at the same alias, this updates it in place.

### Step 5: Trigger on the Feature Branch and Poll

Trigger the pipeline against the branch from Step 3, then poll until terminal.

```
mcp__orchestramcp__start_pipeline(alias="<pipeline-uuid>", branch="<feature-branch>")
mcp__orchestramcp__get_pipeline_run_status(pipeline_run_id="<run-uuid>")
```

Poll `get_pipeline_run_status` until the status is not `RUNNING` or `CREATED`. Report the terminal status and surface the Orchestra UI link:

```
https://app.getorchestra.io/pipeline-runs/<run-uuid>/lineage
```

On failure, call `list_task_runs` (filtered by the run UUID) to find the FAILED task, then `download_task_run_log` for its log. Common causes:
- **Connection misconfiguration** — verify `SNOWFLAKE_CONNECTION` is set correctly and has access to the target schemas.
- **SQL syntax error** — review the failing task's log, fix the SQL in the pipeline YAML, re-import, and retrigger.
- **Threshold too strict** — if data legitimately exceeds the threshold, revisit Step 1 thresholds and update the YAML.
- **Schema or table not found** — confirm names from Step 1 match exactly (Snowflake identifiers are case-sensitive in quoted contexts).

Prompt the user to review the test results and confirm that the assertions raised match expectations before treating the pipeline as production-ready.
