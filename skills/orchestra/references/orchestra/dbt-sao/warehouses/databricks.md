# Source freshness on Databricks (Orchestra SAO)

## The rule: the one warehouse where metadata inference works

Databricks is the **only** warehouse with a registered Orchestra SAO freshness fallback. When you
omit both `loaded_at_field` and `loaded_at_query`, Orchestra runs **`DESCRIBE HISTORY`** on the
source's Delta table to infer `max_loaded_at` — no data scan, no timestamp column required.

So on Databricks you have a genuine choice:

- **Metadata inference (omit `loaded_at_field`)** — simplest; relies on Delta commit history.
- **Explicit `loaded_at_field`** — more precise. `DESCRIBE HISTORY` reflects *any* commit
  (OPTIMIZE, VACUUM, MERGE), so like Snowflake's `LAST_ALTERED` it can over-report freshness. If
  "fresh" must strictly mean "new rows arrived," prefer an explicit field.

## Recommended patterns

Metadata inference (let Orchestra use `DESCRIBE HISTORY`):

```yaml
sources:
  - name: raw
    schema: raw                       # within the catalog
    config:
      freshness:
        warn_after:  { count: 2, period: hour }
        error_after: { count: 8, period: hour }
      # no loaded_at_field -> Orchestra infers via DESCRIBE HISTORY
    tables:
      - name: clickstream
```

Explicit field (more precise):

```yaml
config:
  freshness:
    warn_after:  { count: 2, period: hour }
    error_after: { count: 8, period: hour }
  loaded_at_field: ingested_at        # a Delta column, or _commit_timestamp
```

## Unity Catalog

With Unity Catalog, set the `catalog` on the source/profile so freshness resolves the three-level
name (`catalog.schema.table`).

## Timezone

Databricks `TIMESTAMP` is stored as UTC. If a column holds local/string times, cast and convert
(e.g. `from_utc_timestamp(to_timestamp(loaded_at), '<source-zone>')`). Not relevant when using
`DESCRIBE HISTORY` metadata inference.

## profiles.yml (reference)

```yaml
default:
  target: databricks
  outputs:
    databricks:
      type: databricks
      catalog: main
      schema: analytics
      host: "{{ env_var('DATABRICKS_HOST') }}"
      http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
      token: "{{ env_var('DATABRICKS_TOKEN') }}"
      threads: 4
```

Bottom line: Databricks is the one place you can safely omit `loaded_at_field` and let Orchestra
infer freshness from `DESCRIBE HISTORY` — use an explicit field only when you need commit history
to mean "new data" specifically.
