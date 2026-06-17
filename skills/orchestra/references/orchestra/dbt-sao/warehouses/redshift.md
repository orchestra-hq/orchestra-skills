# Source freshness on Redshift (Orchestra SAO)

## The rule: explicit field required

**Redshift is not in Orchestra's SAO freshness fallback table**, so there is **no Orchestra
metadata fallback** — provide an explicit `loaded_at_field` (or `loaded_at_query`). If you omit
both, Orchestra falls back to dbt's `FreshnessRunner` default, which "may surface as warnings or a
non-actionable result" — not a reliable SAO signal.

> dbt itself can read Redshift table metadata (`SVV_*` / `STL_*` system tables) for freshness, but
> that is dbt behaviour, not Orchestra SAO. For SAO, give an explicit field.

## Recommended pattern

```yaml
sources:
  - name: raw
    schema: raw
    config:
      freshness:
        warn_after:  { count: 2, period: hour }
        error_after: { count: 6, period: hour }
      loaded_at_field: _loaded_at        # required — a timestamp/timestamptz column
    tables:
      - name: orders
      - name: customers
```

For very large tables, a `loaded_at_query` bounded to recent data avoids a full scan:

```yaml
config:
  freshness:
    warn_after: { count: 1, period: hour }
  loaded_at_query: "select max(loaded_at) from {{ this }} where loaded_at > dateadd(day, -7, getdate())"
```

## Metadata-derived freshness — not simple here

Redshift has no single, cheap last-modified column (`SVV_TABLE_INFO` carries no load timestamp;
`STL_INSERT`/`SYS_*` history is complex and permission-gated). Don't try to derive freshness from
metadata — use an explicit `loaded_at_field` (or a bounded `loaded_at_query`) against a real
load-timestamp column. If none exists, ask the user which column marks load time.

## Timezone

Redshift `TIMESTAMP` is zone-naive and assumed UTC; `TIMESTAMPTZ` stores a zone. If a column is
local naive time, convert: `loaded_at_field: "convert_timezone('US/Eastern', 'UTC', loaded_at)"`.

## profiles.yml (reference)

```yaml
default:
  target: redshift
  outputs:
    redshift:
      type: redshift
      host: my-cluster.abc123.us-east-1.redshift.amazonaws.com
      port: 5439
      user: orchestra_user
      password: "{{ env_var('REDSHIFT_PASSWORD') }}"
      dbname: analytics
      schema: raw
      threads: 4
```

Bottom line: on Redshift, **set an explicit `loaded_at_field`** for SAO — don't rely on metadata
inference.
