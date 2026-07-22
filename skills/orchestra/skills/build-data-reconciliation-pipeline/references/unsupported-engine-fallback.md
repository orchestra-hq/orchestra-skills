# Fallback pattern for an unsupported engine

`DATA_RECONCILIATION_MANUAL_QUERY` and `DATA_RECONCILIATION_CURSOR_FIELD` only accept
`SNOWFLAKE`, `SQL_SERVER`, `DATABRICKS` on either side (`DataRecIntegrations` enum). The moment
either system is something else — Postgres, MySQL, Redshift, BigQuery, ... — neither native
task type is usable, no matter how the request is phrased. Say so plainly rather than quietly
substituting this pattern and calling it "the reconciliation pipeline" — it's a materially
weaker fallback (no built-in caching, no built-in threshold engine, no cursor-field drift
monitor), not an equivalent.

Offer the user a choice before building anything: (1) this fallback, hand-rolled with plain
query tasks, or (2) land a copy of the unsupported side's data into one of the three supported
engines first (a one-time or ongoing sync), then get the real native DataRec experience for
every check downstream. Option 2 is worth raising even though it's more work up front — it's
the difference between a bespoke comparison you maintain forever and the platform feature
everything else in this skill assumes.

## The pattern

Two independent query tasks (one per system, each in that system's own integration, e.g.
`POSTGRES_RUN_QUERY` / `SNOWFLAKE_RUN_QUERY`), each with `set_outputs: true`, followed by a
`PYTHON_EXECUTE_SCRIPT` task that reads both outputs and does the diff itself — since there's
no native task type left to do the comparison for you.

```yaml
version: v1
name: 'PROD (Postgres) to MIGRATION (Snowflake) — Fallback Reconciliation #migration #data-reconciliation'
pipeline:
  row_count_checks:
    tasks:
      pg_row_count:
        integration: POSTGRES
        integration_job: POSTGRES_RUN_QUERY
        parameters:
          statement: 'SELECT COUNT(*) AS row_count FROM public.orders'
          set_outputs: true
        depends_on: []
        name: 'Postgres row count'
      sf_row_count:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        parameters:
          statement: 'SELECT COUNT(*) AS row_count FROM MIGRATION.PUBLIC.ORDERS'
          set_outputs: true
        depends_on: []
        name: 'Snowflake row count'
    depends_on: []
    name: 'Row Count Checks'
  comparison:
    tasks:
      compare_row_counts:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        parameters:
          source: INLINE
          code: |
            pg_rows = ${{ ORCHESTRA.PIPELINE_RUN_TASKS['pg_row_count'].OUTPUTS['results'] }}
            sf_rows = ${{ ORCHESTRA.PIPELINE_RUN_TASKS['sf_row_count'].OUTPUTS['results'] }}
            pg_count = pg_rows[0]['row_count']
            sf_count = sf_rows[0]['row_count']
            diff = abs(pg_count - sf_count)
            print(f'Postgres count={pg_count} Snowflake count={sf_count} diff={diff}')
            assert diff == 0, f'Row count mismatch: postgres={pg_count} snowflake={sf_count}'
        depends_on: []
        name: 'Compare row counts'
    depends_on:
    - row_count_checks
    name: 'Comparison'
alerts:
- name: Reconciliation Failure
  statuses: [FAILED, WARNING]
  destinations:
  - integration: SLACK
    destination: '#data-migration'
```

Validated schema-clean against `validate_pipeline`. One thing this has **not** been confirmed
against: the exact runtime shape of `OUTPUTS['results']`. Orchestra's docs describe it only as
"the results of the last executed query, first 1000 rows" — consistent with a list of row
objects (hence indexing `[0]['row_count']` above), but the precise serialization isn't spelled
out anywhere public. Before trusting this in a real cutover, run the two query tasks once on
their own and check what `results` actually looks like (a log, an artifact, or a throwaway
downstream task that just prints it) — adjust the parsing in the Python task to match rather
than assuming the shape above is exactly right.

## Same-connection variant (both sides on one unsupported engine)

The cross-connection pattern above is the general case, but when both tables live in the
**same** unsupported engine's connection (e.g. two BigQuery datasets in one project, two MySQL
databases on one server), there's a simpler option: that engine can join across both tables in
a single query, so one native single-connection task can do the whole comparison — no
`PYTHON_EXECUTE_SCRIPT` task needed at all, and no dependency on the unconfirmed
`OUTPUTS['results']` shape.

For BigQuery specifically, use `GCP_BQ_RUN_TEST` (the same DQ-test task type
`write-bigquery-dq-tests` uses) rather than a true cross-connection task — it already does
exactly what's needed here: run a query, count the rows it returns, compare to a threshold.
Write the query so it returns a row **only when the two tables disagree**, and default to
checking content, not just row count — a `COUNT(*)` match alone says nothing about whether the
actual data matches, and matching counts with silently-different content is exactly the kind of
migration bug this skill exists to catch:

Parameterize the dataset/table names through the matrix and keep the query shape itself on the
task — same principle as the native pattern in `pipeline-patterns.md`: don't precompute a whole
query string per matrix entry when only the table names actually vary.

```yaml
version: v1
name: 'Google Sheets Leads — Reconciliation Validation #bigquery #data-reconciliation'
pipeline:
  table_row_count_parity:
    tasks:
      check_row_count_parity:
        integration: GCP_BIG_QUERY
        integration_job: GCP_BQ_RUN_TEST
        parameters:
          query: >
            select 1 from
            (select count(*) as cnt, sum(farm_fingerprint(to_json_string(t))) as chk
             from `${{ MATRIX.table_checks[''source_dataset''] }}.${{ MATRIX.table_checks[''source_table''] }}` t) as src,
            (select count(*) as cnt, sum(farm_fingerprint(to_json_string(t))) as chk
             from `${{ MATRIX.table_checks[''destination_dataset''] }}.${{ MATRIX.table_checks[''destination_table''] }}` t) as dst
            where src.cnt != dst.cnt or src.chk != dst.chk
          enable_drive_scope: false
          error_threshold_expression: '> 0'
          warn_threshold_expression: '> 0'
        depends_on: []
        name: 'Row count + content parity — ${{ MATRIX.table_checks[''label''] }}'
        connection: ${{ ENV.GCP_BIG_QUERY_CONNECTION }}
    depends_on: []
    name: 'Table Row Count + Content Parity'
    matrix:
      inputs:
        table_checks:
        - label: 'sheet_1_dlt_range vs linkedin'
          source_dataset: google_sheets_data
          source_table: sheet_1_dlt_range
          destination_dataset: gsheets_leads
          destination_table: linkedin
        - label: 'sheet_2_dlt_range vs dbt_community'
          source_dataset: google_sheets_data
          source_table: sheet_2_dlt_range
          destination_dataset: gsheets_leads
          destination_table: dbt_community
alerts:
- name: Reconciliation Failure
  statuses: [FAILED, WARNING]
  destinations:
  - integration: SLACK
    destination: '#data-migration'
```

Validated schema-clean against the live `validate_pipeline` API. `TO_JSON_STRING(t)` serializes
the whole row regardless of column count/names — useful whenever the exact columns aren't known
upfront — and `FARM_FINGERPRINT` hashes it to a 64-bit int; `SUM()` across rows gives an
order-independent aggregate fingerprint of the whole table, so row-order differences between
source and destination don't cause false failures. Table names omit the project prefix here
(BigQuery resolves against the connection's default project) — add an explicit `project` field
per entry and reference it in the query if source and destination datasets live in different GCP
projects.

Other engines: SQL Server has `CHECKSUM_AGG(CHECKSUM(*))`, Snowflake has `BITXOR_AGG(HASH(...))`
(see `query-templates.md` for both, and its "Why not SUM() for a hash checksum" note — the same
overflow this section just fixed for BigQuery applies to any 64-bit hash summed instead of
XOR'd), and most engines have *some* row- or aggregate-level hash function — reach for whichever
is native rather than assuming BigQuery's function names apply elsewhere.

### Prefer a per-row join over an aggregate fingerprint when a natural key exists

The aggregate fingerprint above answers "do these tables match, yes or no" but not "which
rows" — genuinely useful when there's no shared key to join on, but strictly worse than a
per-row comparison whenever one exists (an email, a profile URL, an order id). When a natural
key is present, join source and destination on it directly and compare per row instead:

```sql
select s.<key>
from src s join dst d on s.<key> = d.<key>
where to_json_string(struct(<aligned source columns>)) != to_json_string(struct(<aligned destination columns>))
limit 100
```

This surfaces the actual mismatching keys (visible in the task's violating-row output), not
just an aggregate yes/no. Two things to check before trusting this pattern, both discovered the
hard way reconciling two Google Sheets-derived tables loaded by different tools (dlt vs
Fivetran):

- **Duplicate keys break the join silently** — if the key isn't unique on either side, a plain
  join fans out (one source row can match multiple destination rows and vice versa), corrupting
  the comparison without any error. Add a dedicated duplicate-key check per side (`GROUP BY
  <key> HAVING COUNT(*) > 1`) as its own task, and restrict the content-comparison join to keys
  that are unique on both sides (`WHERE <key> IN (SELECT <key> FROM ... GROUP BY <key> HAVING
  COUNT(*) = 1)`).
- **Two schemas that hold "the same data" rarely have identical columns.** Different ingestion
  tools produce different column sets: renamed columns, swapped types, extra loader-metadata
  columns, and — for dlt specifically — "variant" columns (`<col>__v_text`, `<col>__v_double`,
  ...) that split out values which didn't fit the primary inferred type, needing
  `COALESCE(CAST(<col> AS STRING), <col>__v_text, ...)` to reconstruct one logical value.
  **Profile both schemas and spot-check a handful of joined rows before writing the full
  comparison** — this is what catches systematic-but-benign conversion artifacts (a source
  storing blanks as `''` where the destination uses `NULL`; a raw spreadsheet serial date number
  next to a formatted date string) versus genuine content drift, and it's the user's call, not
  yours, whether an found artifact should be normalized away or kept as a real mismatch —
  they may deliberately want maximum visibility over a quieter but noisier-signal-free check.
  Because the column mapping is genuinely bespoke per schema pair, this content-comparison query
  is a case where writing one query per pair (not matrixed) is the right call — see
  `pipeline-patterns.md`'s parameterization guidance for why that's the exception, not the rule.

## Extending the pattern

- **More checks** (sums, timestamps): add more query-task pairs per check and reference each
  pair's outputs in the Python task, same as `query-templates.md`'s per-engine SQL for the
  native path — the SQL itself doesn't change, only how the comparison is wired.
- **Tolerance instead of exact match**: change the Python assertion's condition
  (`diff == 0` → `diff > <n>`) — since this is a plain script, not a native
  `error_threshold_expression`, there's no integer-only restriction here.
- **Alerting on failure**: a failed assertion fails the Python task, which the pipeline-level
  `alerts` block above already covers — no extra wiring needed.
