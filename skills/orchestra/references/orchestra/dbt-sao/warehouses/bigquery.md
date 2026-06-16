# Source freshness on BigQuery (Orchestra SAO)

## The rule: explicit field required

**BigQuery is not in Orchestra's SAO freshness fallback table**, so there is **no Orchestra
metadata fallback** — provide an explicit `loaded_at_field` (or `loaded_at_query`). If you omit
both, Orchestra falls back to dbt's `FreshnessRunner` default, which "may surface as warnings or
a non-actionable result" — not a reliable SAO signal.

> Why this surprises people: dbt's `dbt-bigquery` adapter *can* compute metadata freshness from
> `INFORMATION_SCHEMA.TABLE_STORAGE` (and has a `bigquery_use_batch_source_freshness` flag). That
> is dbt behaviour, not Orchestra SAO behaviour. For SAO, give an explicit field.

## Recommended pattern — control cost with a partition filter

BigQuery bills per byte scanned, so when you point `loaded_at_field` at a large partitioned
table, add a `filter` on the partition column so the freshness `max()` prunes partitions instead
of scanning the whole table:

```yaml
sources:
  - name: raw
    database: my-gcp-project     # BigQuery project id
    schema: raw_dataset          # BigQuery dataset
    config:
      freshness:
        warn_after:  { count: 1, period: hour }
        error_after: { count: 3, period: hour }
        filter: "_partitiontime >= timestamp_sub(current_timestamp(), interval 2 day)"
      loaded_at_field: event_loaded_at
    tables:
      - name: page_events
```

For a small unpartitioned table, the filter is unnecessary:

```yaml
config:
  freshness:
    warn_after:  { count: 12, period: hour }
    error_after: { count: 24, period: hour }
  loaded_at_field: signup_loaded_at
```

A `loaded_at_query` with the partition bound baked in is an equally good way to cap cost on the
big table.

## Timezone

BigQuery `TIMESTAMP` is UTC; `DATETIME` has no zone. If using a `DATETIME`/local column, convert:
`loaded_at_field: "timestamp(loaded_at, 'America/Los_Angeles')"`.

## profiles.yml (reference)

```yaml
default:
  target: bigquery
  outputs:
    bigquery:
      type: bigquery
      method: service-account
      project: my-gcp-project
      dataset: analytics
      keyfile: "{{ env_var('BIGQUERY_KEYFILE') }}"
      threads: 4
      location: US
```

Bottom line: on BigQuery, **set an explicit `loaded_at_field`** for SAO, and on large partitioned
tables pair it with a partition `filter` (or a partition-bounded `loaded_at_query`) to keep the
freshness check cheap.
