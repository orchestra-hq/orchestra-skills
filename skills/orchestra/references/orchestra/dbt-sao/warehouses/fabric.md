# Source freshness on Microsoft Fabric (Orchestra SAO)

## The rule: explicit field required

Orchestra's SAO guide lists **Microsoft Fabric** as requiring explicit configuration — **no
Orchestra metadata fallback**. Provide an explicit `loaded_at_field` (or `loaded_at_query`). If
you omit both, Orchestra falls back to dbt's `FreshnessRunner` default, which is not a reliable
SAO signal.

This covers the `dbt-fabric` adapter (Fabric Warehouse / Synapse-style T-SQL).

## Recommended pattern

```yaml
sources:
  - name: raw
    schema: raw
    config:
      freshness:
        warn_after:  { count: 2, period: hour }
        error_after: { count: 6, period: hour }
      loaded_at_field: loaded_at         # required — a datetime2 column
    tables:
      - name: orders
      - name: customers
```

For large tables, bound a `loaded_at_query` to recent data:

```yaml
config:
  freshness:
    warn_after: { count: 1, period: hour }
  loaded_at_query: "select max(loaded_at) from {{ this }} where loaded_at > dateadd(day, -7, sysutcdatetime())"
```

## Timezone

T-SQL `datetime2` is zone-naive and assumed UTC; use `sysutcdatetime()` (not `getdate()`) when
deriving "now". If a column is local, convert with `loaded_at_field` SQL
(`CAST(... AT TIME ZONE 'UTC' ...)`) so the comparison is UTC.

## profiles.yml (reference)

```yaml
default:
  target: fabric
  outputs:
    fabric:
      type: fabric
      driver: "ODBC Driver 18 for SQL Server"
      server: "<workspace>.datawarehouse.fabric.microsoft.com"
      database: analytics
      authentication: ServicePrincipal
      tenant_id: "{{ env_var('FABRIC_TENANT_ID') }}"
      client_id: "{{ env_var('FABRIC_CLIENT_ID') }}"
      client_secret: "{{ env_var('FABRIC_CLIENT_SECRET') }}"
      schema: raw
      threads: 4
```

Bottom line: on Microsoft Fabric, **set an explicit `loaded_at_field`** for SAO — there is no
metadata fallback.
