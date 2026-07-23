# Reconciliation pipeline patterns

Structural patterns for the two pipelines this skill produces, plus how to handle scope
that isn't a fixed table list. See `../../../references/orchestra/pipeline/yaml-authoring.md`
for the base schema and `query-templates.md` for the SQL itself.

## Pattern 1 — one task group per check kind, matrixed over checks

`MatrixBlockModel.inputs` is "currently limited to one input key," but that one key's values
can be a list of dicts, not just strings — reference a field with
`${{ MATRIX.<input_name>['<key>'] }}`. Parameterize the **objects that vary** — table name,
column name, dataset — inside one shared query template on the task, rather than precomputing
a whole query string per matrix entry. The query *shape* is identical across every table in a
given check (`SELECT COUNT(*) FROM <table>` for every row-count check, `SELECT SUM(<col>) FROM
<table>` for every sum check); only the table/column names differ, so those are exactly what
the matrix should hold — a matrix value that's itself a full precomputed SQL string duplicates
the shape N times and makes it harder to audit or fix. This is the same pattern the
`write-*-dq-tests` skills use for test catalogues — see
`../../write-databricks-dq-tests/../../references/orchestra/dq-tests/databricks.md` for a
worked example with the identical `MATRIX.dq_inputs['column']` syntax.

Group checks by **kind**, not by table — one task group for row counts (fans out over every
table in scope), one task group for column-level aggregates (fans out over every
table+column+metric check across every table). This keeps the pipeline to a handful of task
groups regardless of how many tables are being reconciled, and matches the report structure
(chat summary "N row-count checks, M column checks" reads better than one line per table).

`error_threshold_expression`/`warn_threshold_expression` must be a **literal string at
authoring time** — `orchestra-cli validate` rejects a matrix-templated value
(`${{ MATRIX.x['error_threshold'] }}`) with "Invalid threshold expression format," even
though the schema's type is just `string` and nothing else about the field hints at that
restriction. So group further by **threshold policy**, not only by check kind: everything in
one task group shares one hardcoded threshold. An exact-match row-count group and a
tolerant-lag timestamp group are two task groups, even though both are "aggregate checks" —
don't try to carry the threshold itself through the matrix like every other per-check value.

```yaml
version: v1
name: 'Orders Migration — Reconciliation Validation #migration #data-reconciliation'
pipeline:
  row_count_checks:
    tasks:
      check_row_count:
        integration: ORCHESTRA
        integration_job: DATA_RECONCILIATION_MANUAL_QUERY
        parameters:
          source_integration: SNOWFLAKE
          destination_integration: DATABRICKS
          source_query: 'SELECT COUNT(*) FROM ${{ MATRIX.table_checks[''source_table''] }}'
          destination_query: 'SELECT COUNT(*) FROM ${{ MATRIX.table_checks[''destination_table''] }}'
          error_threshold_expression: '!= 0'
        depends_on: []
        name: 'Row count — ${{ MATRIX.table_checks[''name''] }}'
    depends_on: []
    name: 'Row Count Checks'
    matrix:
      inputs:
        table_checks:
        - name: orders
          source_table: RAW.PUBLIC.ORDERS
          destination_table: prod.sales.orders
        - name: customers
          source_table: RAW.PUBLIC.CUSTOMERS
          destination_table: prod.sales.customers
  column_sum_checks:
    tasks:
      check_column_sum:
        integration: ORCHESTRA
        integration_job: DATA_RECONCILIATION_MANUAL_QUERY
        parameters:
          source_integration: SNOWFLAKE
          destination_integration: DATABRICKS
          source_query: 'SELECT ROUND(SUM(${{ MATRIX.sum_checks[''column''] }}) * 100) FROM ${{ MATRIX.sum_checks[''source_table''] }}'
          destination_query: 'SELECT ROUND(SUM(${{ MATRIX.sum_checks[''column''] }}) * 100) FROM ${{ MATRIX.sum_checks[''destination_table''] }}'
          error_threshold_expression: '> 100'      # hardcoded: shared by every check in this group
        depends_on: []
        name: '${{ MATRIX.sum_checks[''label''] }}'
    depends_on:
    - row_count_checks
    name: 'Column Sum Checks'
    matrix:
      inputs:
        sum_checks:
        # Scaled to cents (*100, rounded to an integer) because error_threshold_expression only
        # accepts a comparator + non-negative integer -- see query-templates.md. Threshold '> 100'
        # above means "more than $1.00 off." Only the table/column values vary per entry -- the
        # query shape lives once, on the task, not duplicated per matrix row.
        - label: 'orders.total_amount sum (cents)'
          source_table: RAW.PUBLIC.ORDERS
          destination_table: prod.sales.orders
          column: total_amount
  column_timestamp_checks:
    tasks:
      check_column_timestamp:
        integration: ORCHESTRA
        integration_job: DATA_RECONCILIATION_MANUAL_QUERY
        parameters:
          source_integration: SNOWFLAKE
          destination_integration: DATABRICKS
          source_query: 'SELECT DATE_PART(epoch_second, MAX(${{ MATRIX.timestamp_checks[''column''] }})) FROM ${{ MATRIX.timestamp_checks[''source_table''] }}'
          destination_query: 'SELECT unix_timestamp(MAX(${{ MATRIX.timestamp_checks[''column''] }})) FROM ${{ MATRIX.timestamp_checks[''destination_table''] }}'
          error_threshold_expression: '> 60'         # a different policy (seconds of lag) -> its own group
        depends_on: []
        name: '${{ MATRIX.timestamp_checks[''label''] }}'
    depends_on:
    - row_count_checks
    name: 'Column Timestamp Checks'
    matrix:
      inputs:
        timestamp_checks:
        - label: 'orders.created_at max (epoch seconds)'
          source_table: RAW.PUBLIC.ORDERS
          destination_table: prod.sales.orders
          column: created_at
alerts:
- name: Reconciliation Failure
  statuses: [FAILED, WARNING]
  destinations:
  - integration: SLACK
    destination: '#data-migration'
```

Validated schema-clean against the live `validate_pipeline` API — the dialect-specific function
names (`DATE_PART(epoch_second, ...)` vs `unix_timestamp(...)`) stay hardcoded in the query
template since `source_integration`/`destination_integration` are fixed per task, not per matrix
entry; only the table/column values are templated. Splitting into `column_sum_checks` and
`column_timestamp_checks` above is what lets row counts demand an exact match while a
timestamp-lag check tolerates a minute of drift — each group's `error_threshold_expression` is a
plain hardcoded literal. Add another sibling group any time a new check needs a threshold policy
that doesn't already have a group.

### Same-engine variant (e.g. Snowflake account to Snowflake account)

The example above is cross-engine (Snowflake → Databricks), which is why the timestamp check
translates the epoch-seconds function per side (`DATE_PART(epoch_second, ...)` vs
`unix_timestamp(...)`). The other common case this skill covers — migrating between two
databases in the **same** engine, e.g. a `PROD` database into a `MIGRATION` database within one
Snowflake account — is simpler: `source_integration`/`destination_integration` are both the
same value, and every query uses identical SQL on both sides since there's no dialect to
translate.

```yaml
version: v1
name: 'PROD to MIGRATION (Snowflake) — Reconciliation Validation #migration #data-reconciliation'
pipeline:
  row_count_checks:
    tasks:
      check_row_count:
        integration: ORCHESTRA
        integration_job: DATA_RECONCILIATION_MANUAL_QUERY
        parameters:
          source_integration: SNOWFLAKE
          destination_integration: SNOWFLAKE
          source_query: 'SELECT COUNT(*) FROM ${{ MATRIX.table_checks[''source_table''] }}'
          destination_query: 'SELECT COUNT(*) FROM ${{ MATRIX.table_checks[''destination_table''] }}'
          error_threshold_expression: '!= 0'
        depends_on: []
        name: 'Row count — ${{ MATRIX.table_checks[''name''] }}'
    depends_on: []
    name: 'Row Count Checks'
    matrix:
      inputs:
        table_checks:
        - name: orders
          source_table: PROD.PUBLIC.ORDERS
          destination_table: MIGRATION.PUBLIC.ORDERS
        - name: customers
          source_table: PROD.PUBLIC.CUSTOMERS
          destination_table: MIGRATION.PUBLIC.CUSTOMERS
  column_sum_checks:
    tasks:
      check_column_sum:
        integration: ORCHESTRA
        integration_job: DATA_RECONCILIATION_MANUAL_QUERY
        parameters:
          source_integration: SNOWFLAKE
          destination_integration: SNOWFLAKE
          source_query: 'SELECT ROUND(SUM(${{ MATRIX.sum_checks[''column''] }}) * 100) FROM ${{ MATRIX.sum_checks[''source_table''] }}'
          destination_query: 'SELECT ROUND(SUM(${{ MATRIX.sum_checks[''column''] }}) * 100) FROM ${{ MATRIX.sum_checks[''destination_table''] }}'
          error_threshold_expression: '> 100'      # tolerance: more than $1.00 off, in cents
        depends_on: []
        name: '${{ MATRIX.sum_checks[''label''] }}'
    depends_on:
    - row_count_checks
    name: 'Column Sum Checks'
    matrix:
      inputs:
        sum_checks:
        - label: 'orders.total_amount sum (cents)'
          source_table: PROD.PUBLIC.ORDERS
          destination_table: MIGRATION.PUBLIC.ORDERS
          column: total_amount
  column_timestamp_checks:
    tasks:
      check_column_timestamp:
        integration: ORCHESTRA
        integration_job: DATA_RECONCILIATION_MANUAL_QUERY
        parameters:
          source_integration: SNOWFLAKE
          destination_integration: SNOWFLAKE
          source_query: 'SELECT DATE_PART(epoch_second, MAX(${{ MATRIX.timestamp_checks[''column''] }})) FROM ${{ MATRIX.timestamp_checks[''source_table''] }}'
          destination_query: 'SELECT DATE_PART(epoch_second, MAX(${{ MATRIX.timestamp_checks[''column''] }})) FROM ${{ MATRIX.timestamp_checks[''destination_table''] }}'
          error_threshold_expression: '> 60'        # tolerance: up to a minute of lag
        depends_on: []
        name: '${{ MATRIX.timestamp_checks[''label''] }}'
    depends_on:
    - row_count_checks
    name: 'Column Timestamp Checks'
    matrix:
      inputs:
        timestamp_checks:
        - label: 'orders.updated_at max (epoch seconds)'
          source_table: PROD.PUBLIC.ORDERS
          destination_table: MIGRATION.PUBLIC.ORDERS
          column: updated_at
alerts:
- name: Reconciliation Failure
  statuses: [FAILED, WARNING]
  destinations:
  - integration: SLACK
    destination: '#data-migration'
```

Validated schema-clean against the live `validate_pipeline` API. Same threshold-policy-per-group
rule applies here too — row counts are exact-match, sums tolerate a dollar, timestamps tolerate
a minute, and `Column Sum Checks`/`Column Timestamp Checks` both depend on `Row Count Checks` so
the cheap check fails fast before the heavier aggregate queries run.

## Pattern 2 — cursor field, matrixed over tables, for the ongoing monitor

Once the cutover has been validated, switch to `DATA_RECONCILIATION_CURSOR_FIELD` for routine
scheduled checks: it only scans rows past the last cached cursor value, so it's far cheaper
to run on a schedule than re-running the full manual-query check every time. Needs a
monotonically-increasing column per table (an identity/auto-increment id, or an
always-increasing `updated_at`) — ask the user which column that is per table rather than
guessing; a column that isn't truly monotonic will produce false drift signals.

```yaml
version: v1
name: 'Orders Migration — Ongoing Drift Monitor #migration #data-reconciliation'
pipeline:
  cursor_checks:
    tasks:
      check_cursor_drift:
        integration: ORCHESTRA
        integration_job: DATA_RECONCILIATION_CURSOR_FIELD
        parameters:
          source_integration: SNOWFLAKE
          destination_integration: DATABRICKS
          source_table_name: ${{ MATRIX.cursor_checks['source_table'] }}
          destination_table_name: ${{ MATRIX.cursor_checks['destination_table'] }}
          source_column_name: ${{ MATRIX.cursor_checks['source_column'] }}
          destination_column_name: ${{ MATRIX.cursor_checks['destination_column'] }}
          detect_count_drift: true
          detect_max_drift: true
        depends_on: []
        name: 'Cursor drift — ${{ MATRIX.cursor_checks[''name''] }}'
    depends_on: []
    name: 'Cursor Field Checks'
    matrix:
      inputs:
        cursor_checks:
        - name: orders
          source_table: RAW.PUBLIC.ORDERS
          destination_table: prod.sales.orders
          source_column: updated_at
          destination_column: updated_at
schedule:
- name: Hourly drift check
  cron: 0 * ? * * *
  timezone: UTC
alerts:
- name: Drift Detected
  statuses: [FAILED, WARNING]
  destinations:
  - integration: SLACK
    destination: '#data-migration'
```

`detect_count_drift`/`detect_max_drift` default thresholds (`> 0` for both) already fail on
any drift — that's usually right for a monitor watching a supposedly-in-sync pair, so there's
rarely a need to override them. `cursor_field_cache_override` exists for the case where the
initial load predates the cache (or the very first run would otherwise fail on a backlog that
isn't actually drift) — set it to the known-good starting cursor value once, at setup time.

## Resolving table/column scope when it isn't a fixed list

Two situations, handled differently:

**The user names specific tables** (with or without their columns) — use that list directly.
If columns for the aggregate checks aren't given, ask which columns matter (keys, monetary
amounts, timestamps, anything the user calls "high risk") rather than enumerating every
column of a wide table — a 200-column table doesn't need 200 null-count checks, and the ones
that do matter get lost in the noise of the ones that don't.

**The user names a schema/database, not specific tables** — you (the assistant building this
pipeline) very likely don't have a live connection to query the warehouses yourself. Two
honest options, and it's worth asking the user which fits:

1. **Ask them to paste the table/column list** — e.g. the output of an
   `information_schema.tables`/`columns` query they run themselves — and treat it as the
   explicit list from there. This keeps the pipeline fully static, which is easier to review,
   diff in a PR, and validate before anything runs.
2. **Build a self-discovering pipeline** — add a task per side (`SNOWFLAKE_RUN_QUERY` /
   `SQL_SERVER_RUN_QUERY` / `DATABRICKS_EXECUTE_STATEMENT`, matching each side's integration)
   that queries `information_schema.tables` for the named schema with `set_outputs: true`,
   then reference that output as the matrix's list via an Orchestra expression instead of a
   static array — e.g. `table_checks: ${{ ORCHESTRA.PIPELINE_RUN_TASKS['discover-tables'].OUTPUTS['results'] }}`.
   This is worth the extra complexity only when the table set is expected to keep changing
   (so the pipeline shouldn't need hand-editing every time a table is added) — for a one-time
   migration cutover, the static list from option 1 is simpler and easier to trust.

Either way, never invent a table or column name to fill a gap — a wrong guess doesn't fail
loudly at authoring time, it fails (or worse, silently reports a meaningless number) on
cutover day.
