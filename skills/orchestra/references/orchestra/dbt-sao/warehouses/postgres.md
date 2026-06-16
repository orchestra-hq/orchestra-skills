# Source freshness on PostgreSQL (Orchestra SAO)

## The rule: explicit field required

Orchestra's SAO guide lists **PostgreSQL** as requiring explicit configuration — **no Orchestra
metadata fallback**. Provide an explicit `loaded_at_field` (or `loaded_at_query`). Omitting both
leaves SAO without a reliable freshness signal (it falls through to dbt's `FreshnessRunner`
default).

## Recommended pattern

```yaml
sources:
  - name: raw
    schema: raw
    config:
      freshness:
        warn_after:  { count: 2, period: hour }
        error_after: { count: 6, period: hour }
      loaded_at_field: loaded_at         # required — a timestamp/timestamptz column
    tables:
      - name: orders
      - name: customers
```

For large tables, bound a `loaded_at_query` to recent data:

```yaml
config:
  freshness:
    warn_after: { count: 1, period: hour }
  loaded_at_query: "select max(loaded_at) from {{ this }} where loaded_at > now() - interval '7 days'"
```

## Metadata-derived freshness — not simple here

Postgres catalog stats (`pg_stat_user_tables.last_autovacuum`/`last_analyze`) track maintenance,
not data loads, so there's no cheap, reliable last-load timestamp to derive freshness from. Use an
explicit `loaded_at_field` against a real load-timestamp column; if none exists, ask the user.

## Timezone

Postgres `timestamp` (without time zone) is assumed UTC; `timestamptz` carries a zone. If a column
is local naive time, convert: `loaded_at_field: "loaded_at at time zone 'US/Eastern' at time zone 'UTC'"`.

## profiles.yml (reference)

```yaml
default:
  target: postgres
  outputs:
    postgres:
      type: postgres
      host: db.example.com
      port: 5432
      user: orchestra_user
      password: "{{ env_var('POSTGRES_PASSWORD') }}"
      dbname: analytics
      schema: raw
      threads: 4
```

Bottom line: on PostgreSQL, **set an explicit `loaded_at_field`** for SAO — there is no metadata
fallback.
