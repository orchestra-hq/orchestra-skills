# dbt `build_after` — schema reference

`build_after` is the per-model side of state-aware orchestration. Where source freshness answers
"is there new upstream data?", `build_after` answers "given that, should *this* model rebuild
yet?". It is **warehouse-agnostic** — it is pure dbt model metadata that Orchestra evaluates, so
the same config works on Snowflake, BigQuery, Databricks, and MotherDuck. The only warehouse
nuance lives upstream in the freshness signal it consumes (see `source-freshness.md`).

## What it does

A model with `build_after` rebuilds only when **both** hold:

1. enough time has elapsed since its last build (`count` + `period`), **and**
2. its upstream data is fresh (per `updates_on`).

This sets an effective per-model SLA and stops needless rebuilds when nothing upstream changed.

## Where it goes

In the dbt project's model config — either in the model's YAML `config:` block or in
`dbt_project.yml` under `models:`. Match wherever the project already configures models.

```yaml
models:
  - name: dim_orders
    config:
      freshness:
        build_after:
          count: 2
          period: hour
          updates_on: all      # wait until ALL upstreams are fresh
  - name: fct_revenue
    config:
      freshness:
        build_after:
          count: 1
          period: hour         # updates_on omitted -> defaults to "any"
```

Equivalent in `dbt_project.yml`:

```yaml
models:
  my_project:
    marts:
      +freshness:
        build_after:
          count: 1
          period: hour
          updates_on: any
```

## Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `count` | yes | Positive integer; with `period`, the minimum elapsed time since last build. |
| `period` | yes | `minute` \| `hour` \| `day`. |
| `updates_on` | no | `any` (rebuild as soon as *any* upstream is fresh) or `all` (wait for *all* upstreams). **Defaults to `any`.** |

`build_after` intent propagates up the DAG to parent models, so freshness expectations flow
upstream — you don't have to annotate every intermediate model to get sensible behaviour.

## Choosing values

`updates_on` follows from the DAG: **`all`** for models that must reflect every upstream (e.g. a
join across several fact sources where a partial refresh would mislead), **`any`** (default) for
models where any new upstream data is worth a rebuild. You can read this off the model SQL.

`count`/`period` is the model's **SLA** — a business decision, not something to guess. **Ask the
user first**: they often already know the target (e.g. "marts must be no more than an hour stale").
Only reach for warehouse usage if they don't know and want you to estimate it. Settle it one of
two ways:

### Approach A — derive the SLA from warehouse usage (only if the user asks)

If the client can run read-only queries against the warehouse, estimate how often each model is
actually consumed (or how often its upstreams refresh) and propose an SLA from that — e.g. a mart
queried ~hourly → `count: 1, period: hour`. Representative starting queries (adapt names/permissions):

- **Snowflake** — reads against the table over the last 7 days:
  ```sql
  select count(*) as reads_7d
  from snowflake.account_usage.access_history,
       lateral flatten(base_objects_accessed) o
  where o.value:objectName::string = 'ANALYTICS.MARTS.FCT_ORDERS'
    and query_start_time > dateadd(day, -7, current_timestamp());
  ```
- **BigQuery** — jobs that referenced the table:
  ```sql
  select count(*) as reads_7d
  from `region-us`.INFORMATION_SCHEMA.JOBS, unnest(referenced_tables) rt
  where rt.table_id = 'fct_orders' and creation_time > timestamp_sub(current_timestamp(), interval 7 day);
  ```
- **Databricks** — `system.access.audit` / query-history system tables filtered to the table.
- **Redshift / Postgres / others** — query-history is harder/permission-gated; if it isn't cheap,
  fall back to Approach B rather than spelunking.

Turn the cadence into an SLA (busy hourly read pattern → hourly; daily reporting table → daily).
**Always show the user the derived number and the evidence, and let them confirm or override** —
usage is a proxy for the SLA, not the SLA itself.

### Approach B — user-defined SLAs (the default)

Take the SLA the user gives you, per model or as a marts-wide default. This is the expected path —
the SLA is usually a known business commitment, so prompt for it before considering Approach A.

Default behaviour: **ask first.** Only run a usage query if the user opts in. If the user has no
SLA and doesn't want the usage path, leave a clearly-marked placeholder as a last resort and
explain the trade-off (too tight rebuilds needlessly; too loose breaches the SLA).

## Dependency on source freshness

`build_after` is only meaningful once the upstream sources have freshness configured — otherwise
"is upstream fresh?" has no answer and the gate can't work as intended. If the project has no
source freshness yet, pair this with `configure-dbt-source-freshness` and say so in the handoff.
