# Reconciliation query templates by engine

`DATA_RECONCILIATION_MANUAL_QUERY` runs `source_query` against the source engine and
`destination_query` against the destination engine **independently** — there is no
cross-system join, because the two sides are different connections (possibly different
warehouses entirely). Every query must resolve to **one column, one row** — a single
scalar. That rules out `SELECT *`, multi-row `GROUP BY`, and anything returning more than
one value. Build the comparison as a set of scalar checks (count, sum, min/max, distinct
count, checksum) rather than expecting a row-level diff — that's the practical proxy for
"do these match" when you can't join across systems.

Each engine section below covers: identifier qualification, row count, per-column-kind
aggregate, and an optional row-checksum aggregate. Mix and match — source and destination
don't have to be the same engine (that's the whole point of this skill).

## Snowflake

- Qualify as `DATABASE.SCHEMA.TABLE` (or `SCHEMA.TABLE` if the connection's default database
  covers it — match whatever the pipeline's other Snowflake tasks in the repo already do).
- Row count: `SELECT COUNT(*) FROM DATABASE.SCHEMA.TABLE`
- Numeric column sum: `SELECT SUM(<col>) FROM DATABASE.SCHEMA.TABLE`
- Null count (any column): `SELECT COUNT(*) - COUNT(<col>) FROM DATABASE.SCHEMA.TABLE`
- Distinct count (string/categorical): `SELECT COUNT(DISTINCT <col>) FROM DATABASE.SCHEMA.TABLE`
- Timestamp min/max **as a number** (see "Why epoch-seconds" below):
  `SELECT DATE_PART(epoch_second, MAX(<col>)) FROM DATABASE.SCHEMA.TABLE`
- Boolean true-count: `SELECT SUM(IFF(<col>, 1, 0)) FROM DATABASE.SCHEMA.TABLE`
- Row checksum (optional, stronger check — order-independent, not cryptographic):
  `SELECT BITXOR_AGG(HASH(<col1>, <col2>, <col3>, ...)) FROM DATABASE.SCHEMA.TABLE` — list
  every column you want covered. Use `BITXOR_AGG`, not `SUM`: `HASH()` returns a signed 64-bit
  int already near the full range, so `SUM()` across more than a couple of rows overflows
  `INT64` (confirmed as a real production failure on BigQuery's equivalent — see the Databricks
  section below and the "why not SUM" note after this table). `BITXOR_AGG` is still
  order-independent, just via bitwise XOR instead of addition, so it can't overflow.

## SQL Server

- Qualify as `[Database].[Schema].[Table]` — bracket-quote when the name has a space,
  reserved word, or mixed case that the connection's collation might otherwise mangle.
- Row count: `SELECT COUNT(*) FROM [Database].[Schema].[Table]`
- Numeric column sum: `SELECT SUM([<col>]) FROM [Database].[Schema].[Table]`
- Null count: `SELECT COUNT(*) - COUNT([<col>]) FROM [Database].[Schema].[Table]`
- Distinct count: `SELECT COUNT(DISTINCT [<col>]) FROM [Database].[Schema].[Table]`
- Timestamp min/max as a number:
  `SELECT DATEDIFF(SECOND, '1970-01-01', MAX([<col>])) FROM [Database].[Schema].[Table]`
- Boolean/bit true-count: `SELECT SUM(CAST([<col>] AS INT)) FROM [Database].[Schema].[Table]`
- Row checksum (optional, stronger check): SQL Server has a purpose-built aggregate for this —
  `SELECT CHECKSUM_AGG(CHECKSUM(*)) FROM [Database].[Schema].[Table]`, or
  `CHECKSUM_AGG(CHECKSUM([<col1>], [<col2>], ...))` to cover a specific column subset.

## Databricks (Unity Catalog / Spark SQL)

- Qualify as `catalog.schema.table` (Unity Catalog) or `hive_metastore.schema.table` for a
  legacy metastore — check which one the connection actually points at before assuming.
- Row count: `SELECT COUNT(*) FROM catalog.schema.table`
- Numeric column sum: `SELECT SUM(<col>) FROM catalog.schema.table`
- Null count: `SELECT COUNT(*) - COUNT(<col>) FROM catalog.schema.table`
- Distinct count: `SELECT COUNT(DISTINCT <col>) FROM catalog.schema.table`
- Timestamp min/max as a number:
  `SELECT unix_timestamp(MAX(<col>)) FROM catalog.schema.table`
- Boolean true-count: `SELECT SUM(CAST(<col> AS INT)) FROM catalog.schema.table`
- Row checksum (optional, stronger check — Spark's `hash()` is 32-bit and can wrap on huge
  tables, so treat it as a heuristic, not a cryptographic guarantee):
  `SELECT bit_xor(hash(<col1>, <col2>, <col3>, ...)) FROM catalog.schema.table` — prefer
  `bit_xor` over `sum` here too (see the note below the engine tables); `hash()`'s 32-bit
  output makes overflow less likely than Snowflake/BigQuery's 64-bit hashes, but `bit_xor` is
  the same cost and removes the risk entirely rather than relying on "less likely."

## Why not SUM() for a hash checksum

`SUM()` over a hash function's output is a natural first instinct for "one order-independent
number representing the whole table," but it's the wrong aggregate: a 64-bit hash (Snowflake's
`HASH()`, BigQuery's `FARM_FINGERPRINT()`) is already spread across nearly the full `INT64`
range, so summing more than a couple of rows' worth exceeds it — this hit a real BigQuery
pipeline mid-session with `Error in SUM aggregation: integer overflow`. A bitwise `XOR`
aggregate (`BITXOR_AGG` on Snowflake, `BIT_XOR` on BigQuery/Spark) gives the same
order-independence — XOR-ing a set of values in any order produces the same result — without
ever growing in magnitude, so it structurally can't overflow. Reach for whichever bitwise
aggregate the engine provides before reaching for `SUM` on a hash column.

## Schema / column parity — a check kind, not just an authoring step

Two ingestion tools loading "the same data" rarely produce identical schemas: extra
lineage/loader-metadata columns (dlt's `_dlt_load_id`/`_dlt_id`), split "variant" columns,
renamed or retyped columns. A row-count and content check can pass cleanly while the schema
has already drifted underneath it — this was discovered the hard way reconciling a
dlt-loaded Google Sheets table against a natively-loaded one (see
`unsupported-engine-fallback.md`'s same-connection example). Treat schema parity as its own
check, not something eyeballed once while writing the content query.

`DATA_RECONCILIATION_MANUAL_QUERY` can't join across connections, so reduce the column list to
a single-scalar fingerprint the same way as the row checksum above: hash `column_name` +
`data_type` for the columns actually expected to match on both sides (ask the user which
columns those are — this must be the *shared* business columns, not every column a loader
happens to add), XOR-aggregate for order independence, and compare source vs destination as
one number.

- Snowflake: `SELECT BITXOR_AGG(HASH(COLUMN_NAME || ':' || DATA_TYPE)) FROM
  INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '<SCHEMA>' AND TABLE_NAME = '<TABLE>' AND
  COLUMN_NAME IN (<expected columns>)`
- SQL Server (no `BITXOR_AGG`; `CHECKSUM_AGG` is the equivalent order-independent aggregate):
  `SELECT CHECKSUM_AGG(CHECKSUM(COLUMN_NAME + ':' + DATA_TYPE)) FROM
  INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '<Schema>' AND TABLE_NAME = '<Table>' AND
  COLUMN_NAME IN (<expected columns>)`
- Databricks: `SELECT bit_xor(hash(concat(column_name, ':', data_type))) FROM
  information_schema.columns WHERE table_schema = '<schema>' AND table_name = '<table>' AND
  column_name IN (<expected columns>)`
- BigQuery: `SELECT bit_xor(farm_fingerprint(concat(column_name, ':', data_type))) FROM
  <dataset>.INFORMATION_SCHEMA.COLUMNS WHERE table_name = '<table>' AND column_name IN
  (<expected columns>)`

The column list is itself a query-shape input that varies per table pair, unlike every other
check above — that's a legitimate exception to "don't precompute the query string," the same
one `unsupported-engine-fallback.md` already carves out for bespoke content-comparison joins.

When both sides live in the **same** connection (the BigQuery same-connection fallback
pattern, or any engine where source and destination share one connection), prefer a direct
`LEFT JOIN` between the two sides' `INFORMATION_SCHEMA.COLUMNS` over the hash — it's one query
instead of two, and it tells you *which* column differs instead of just yes/no. See
`unsupported-engine-fallback.md` for the worked example. Reach for the hash-fingerprint form
above only when source and destination are genuinely different connections, i.e. whenever
`DATA_RECONCILIATION_MANUAL_QUERY`'s one-query-per-side constraint applies. Both forms
(`GCP_BQ_RUN_TEST` running the join, `DATA_RECONCILIATION_MANUAL_QUERY` running the two
hashes) validate schema-clean against `validate_pipeline` — the join form hasn't been run
against live BigQuery data, so spot-check its output once before trusting it in a real
pipeline, same caveat as the fallback doc's `OUTPUTS['results']` note.

**Default to warn, not error.** Unlike row-count or content drift, a schema mismatch on
loader-added columns is often expected and benign (that's the entire premise above), so
failing the pipeline on it produces alert fatigue rather than a real finding. The two task
types differ in how "warn only" is actually expressed, and it is easy to get backwards:

- `DATA_RECONCILIATION_MANUAL_QUERY` (native path): `error_threshold_expression` and
  `warn_threshold_expression` both default to `null` — see "Threshold expressions" below. So
  warn-only here is simply: set `warn_threshold_expression: '!= 0'` and **omit**
  `error_threshold_expression` entirely.
- `GCP_BQ_RUN_TEST` (the BigQuery fallback path): both thresholds default to `'> 0'` if
  omitted, so leaving `error_threshold_expression` unset still fails the task on any drift.
  Warn-only here requires explicitly setting it to something the check can never reach (e.g.
  `'> 999999'`) — omitting it does **not** give warn-only, it gives error-on-any-drift, the
  opposite of what's wanted.

Only escalate to an error threshold if the user has explicitly said the two schemas must
match exactly (e.g. reconciling two loads from the same tool, where any drift really is a
bug).

## Why epoch-seconds for timestamps

Per Orchestra's docs, `error_threshold_expression`/`warn_threshold_expression` are only
evaluated when **both** query results are numeric (int or float) — the threshold is checked
against the *difference* between source and destination. A raw timestamp or string result
falls outside that documented behavior, so cast every comparison to a number:
counts, sums, epoch-seconds for dates, hash aggregates for content. This also has a real
practical benefit for timestamps specifically: converting to epoch-seconds lets you set a
tolerance (`> 60` = "within a minute is fine") instead of demanding bit-for-bit equality,
which matters when the two engines round or truncate sub-second precision differently.

If a check genuinely can't be expressed as a number (e.g. comparing a status string), don't
assume Orchestra silently does the right thing — run that one task on its own first and
confirm it actually fails when you feed it two different strings, before relying on it in a
migration-day pipeline.

## Threshold expressions — the one thing you must never skip

`error_threshold_expression` and `warn_threshold_expression` are both optional in the schema,
but that "optional" is a trap: if neither is set, the task **always succeeds**, regardless of
how different the two numbers are — Orchestra just runs both queries and reports the values.
Every `DATA_RECONCILIATION_MANUAL_QUERY` task this skill produces must set at least
`error_threshold_expression` explicitly.

**The expression format is stricter than the schema lets on.** The field type is just
`string`, but the live validator (confirmed against `validate_pipeline`) rejects anything
that isn't a comparator directly followed by a **non-negative integer** — no decimals, no
negative numbers, no matrix/variable templating (see `pipeline-patterns.md`'s threshold-policy
note for that last one). Confirmed-valid forms: `!= 0`, `> 0`, `>= 5` (spacing before the
number is optional). Confirmed-**invalid**: `> 0.01` (decimal), `> -5` (negative), and any
`${{ ... }}` expression. This matters most for monetary `SUM()` checks, where a natural
tolerance is fractional (a cent) — you can't express "> $0.01" directly:
- Prefer exact match (`!= 0`) for a cutover check — it's an integer-compatible ask anyway.
- If a tolerance is genuinely needed on a fractional metric, scale the query into an integer
  unit before comparing (e.g. `SUM(total_amount * 100)` for cents) so the threshold can be a
  whole number in that scaled unit (`> 100` = "more than $1.00 off in cents").

Defaults to reach for:
- **Migration cutover / one-off validation**: exact match, `!= 0` — during a cutover the two
  systems should be identical, so any non-zero difference is a real finding, not noise, and
  it sidesteps the integer-only restriction entirely.
- **Ongoing reconciliation while the source is still being written to** (e.g. reconciling
  against a live system mid-migration, or comparing a slightly-lagged replica): a small
  integer tolerance is legitimate — `> <n>` where `<n>` reflects genuine expected lag (a few
  rows, a few seconds of epoch difference), not a number picked to make the pipeline green.
  Ask the user what tolerance is actually acceptable rather than guessing one.
