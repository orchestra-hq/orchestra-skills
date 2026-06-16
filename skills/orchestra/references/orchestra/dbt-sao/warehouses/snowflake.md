# Source freshness on Snowflake (Orchestra SAO)

## The rule: explicit field required

Under **Orchestra state-aware orchestration, Snowflake has no metadata fallback** — Orchestra's
state-management guide lists it as "use `loaded_at_field` or `loaded_at_query`". So you **must**
provide an explicit `loaded_at_field` (or `loaded_at_query`); do not omit both and expect
metadata inference.

> Why this surprises people: dbt *itself* can compute Snowflake freshness from `LAST_ALTERED` in
> `INFORMATION_SCHEMA` without a `loaded_at_field`. But Orchestra SAO does not register that
> fallback, and `LAST_ALTERED` is inaccurate anyway (it bumps on *any* DDL — clustering, grants —
> not just data loads). For SAO, always give an explicit field.

## Recommended pattern

```yaml
sources:
  - name: raw
    schema: raw
    config:
      freshness:
        warn_after:  { count: 2, period: hour }
        error_after: { count: 6, period: hour }
      loaded_at_field: _fivetran_synced   # required — or LOADED_AT, CREATED_AT, etc.
    tables:
      - name: orders
      - name: customers
```

For high-frequency tables, a `loaded_at_query` avoids scanning the whole table:

```yaml
config:
  freshness:
    warn_after: { count: 1, period: hour }
  loaded_at_query: "select max(loaded_at) from {{ this }} where loaded_at > dateadd(day, -7, current_timestamp())"
```

## Metadata-derived freshness (when there's no load-timestamp column)

If a source has no obvious load/sync column, Snowflake exposes a last-modified time cheaply via
`INFORMATION_SCHEMA.TABLES.LAST_ALTERED` — point `loaded_at_query` at it instead of scanning data:

```yaml
config:
  freshness:
    warn_after:  { count: 2, period: hour }
    error_after: { count: 6, period: hour }
  loaded_at_query: "select last_altered from analytics.information_schema.tables where table_schema = 'RAW' and table_name = 'ORDERS'"
```

Fill in the source's database (`<db>.information_schema.tables`), schema, and table; Snowflake
identifiers are upper-case by default. **Caveat:** `LAST_ALTERED` bumps on *any* change (DDL,
re-clustering, grants), not just loads — so it can over-report freshness. Use a real
`loaded_at_field` when you need "fresh" to strictly mean new rows; use this when you just need a
cheap "has it changed?" signal and no column exists.

## Timezone

Snowflake `TIMESTAMP_NTZ` columns carry no zone — dbt assumes UTC. If the column is local time,
convert: `loaded_at_field: "convert_timezone('America/New_York', 'UTC', loaded_at)"`.

## profiles.yml (reference)

```yaml
default:
  target: snowflake
  outputs:
    snowflake:
      type: snowflake
      account: ABCDEFG-1234567
      user: ORCHESTRA_USER
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      role: ORCHESTRA_ROLE
      warehouse: COMPUTE_WH
      database: ANALYTICS
      schema: RAW
      threads: 4
```

Bottom line: on Snowflake, **never rely on metadata inference for SAO** — set an explicit
`loaded_at_field` (or `loaded_at_query`) on every source you want gated.
