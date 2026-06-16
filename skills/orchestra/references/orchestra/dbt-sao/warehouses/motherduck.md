# Source freshness on MotherDuck / DuckDB (Orchestra SAO)

## The rule: explicit field required

Orchestra's SAO guide lists DuckDB as **not supported** for metadata freshness — there is no
Orchestra fallback. DuckDB (and therefore MotherDuck, which runs the DuckDB engine) does not
expose the metadata Orchestra would need to infer freshness.

**You must provide an explicit `loaded_at_field` or `loaded_at_query`.** Omitting both will not
fall back to metadata — freshness simply won't compute. This is the most common mistake on
MotherDuck, so make the explicit field non-negotiable in anything you author here. (Databricks is
the only warehouse where omitting the field works under SAO.)

## Recommended pattern

```yaml
sources:
  - name: raw
    schema: main                      # DuckDB schema
    config:
      freshness:
        warn_after:  { count: 6,  period: hour }
        error_after: { count: 24, period: hour }
      loaded_at_field: loaded_at       # REQUIRED — there is no metadata fallback
    tables:
      - name: orders
      - name: customers
```

For a large table, narrow the scan with a `loaded_at_query`:

```yaml
config:
  freshness:
    warn_after: { count: 2, period: hour }
  loaded_at_query: "select max(loaded_at) from orders where loaded_at > now() - interval 7 day"
```

## Timezone

DuckDB `TIMESTAMP` is zone-naive and assumed UTC. If the column is local, convert with
`timezone('UTC', loaded_at)` or cast a string column: `loaded_at_field: "loaded_at::timestamp"`.

## profiles.yml (reference)

```yaml
default:
  target: motherduck
  outputs:
    motherduck:
      type: duckdb
      path: "md:analytics"            # MotherDuck database; "md:" prefix
      threads: 4
      # token via env: motherduck_token in extensions/config or MOTHERDUCK_TOKEN env var
```

Bottom line: on MotherDuck/DuckDB there is no metadata shortcut — always specify
`loaded_at_field` (or `loaded_at_query`). If you can't identify a timestamp column, ask the user
which column marks load time rather than omitting it.
