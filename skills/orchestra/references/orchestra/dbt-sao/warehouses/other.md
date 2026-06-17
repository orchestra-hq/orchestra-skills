# Source freshness on other warehouses (Orchestra SAO catch-all)

Use this when the dbt `profiles.yml` `type:` is **not** one of the warehouses with its own file
(Snowflake, BigQuery, Databricks, MotherDuck/DuckDB, Redshift, Microsoft Fabric, PostgreSQL) —
e.g. Trino/Starburst, ClickHouse, Athena, Synapse (non-Fabric), Materialize, DuckDB-on-disk, etc.

## The rule: assume no fallback — explicit field required

Per Orchestra's SAO guide, adapters not in its fallback table have **"No Orchestra fallback unless
listed above; use `loaded_at_*` or verify dbt's default behaviour for your warehouse."** Databricks
is the *only* warehouse with a registered metadata fallback (`DESCRIBE HISTORY`). So for any
unlisted warehouse, the safe and correct default is an explicit `loaded_at_field` (or
`loaded_at_query`).

If you omit both, Orchestra follows dbt's `FreshnessRunner` default for that adapter, "which may
surface as warnings or a non-actionable result" — i.e. SAO may have no usable freshness signal.

## Recommended pattern

```yaml
sources:
  - name: raw
    schema: raw
    config:
      freshness:
        warn_after:  { count: 2, period: hour }
        error_after: { count: 6, period: hour }
      loaded_at_field: loaded_at         # required — a load-timestamp column on the source
    tables:
      - name: orders
      - name: customers
```

When a `max(loaded_at_field)` scan is expensive, use a `loaded_at_query` bounded to recent data
(adapt the SQL dialect — `now()`, `current_timestamp`, `getdate()`, etc.):

```yaml
config:
  freshness:
    warn_after: { count: 1, period: hour }
  loaded_at_query: "select max(loaded_at) from {{ this }} where loaded_at > current_timestamp - interval '7' day"
```

## Checklist for an unlisted warehouse

1. Identify a reliable load-timestamp column on each source (ask the user if unclear — don't guess).
2. Set `loaded_at_field` (or a bounded `loaded_at_query` on large tables).
3. Ensure the comparison is in UTC — cast/convert local timestamps inside the field.
4. **No load column?** Check whether the warehouse exposes a *simple* last-modified time in a
   metadata view (the way Snowflake has `LAST_ALTERED` and BigQuery has `__TABLES__.last_modified_time`).
   If it does and the query is cheap, point a `loaded_at_query` at it — and warn the user it
   reflects any change, not just loads. If metadata access is complex or permission-gated, don't —
   fall back to asking for a real column.
5. Only attempt warehouse-native metadata *inference* (omitting both settings) if you've confirmed
   dbt's behaviour for that adapter; under Orchestra SAO only Databricks is guaranteed. Default to
   an explicit field/query.

Bottom line: outside Databricks, **always set an explicit `loaded_at_field`** for SAO unless you've
verified the adapter behaves otherwise.
