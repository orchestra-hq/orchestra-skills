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

- **`period`/`count`** = the model's target SLA. A mart refreshed hourly → `count: 1, period: hour`.
- **`updates_on: all`** for models that must reflect every upstream (e.g. a join across several
  fact sources where a partial refresh would mislead). **`updates_on: any`** (default) for models
  where any new upstream data is worth a rebuild.

When the right SLA isn't obvious, ask or leave a marked placeholder and explain the trade-off,
rather than inventing a number. An overly tight `build_after` rebuilds too often; too loose and
data goes stale past its SLA.

## Dependency on source freshness

`build_after` is only meaningful once the upstream sources have freshness configured — otherwise
"is upstream fresh?" has no answer and the gate can't work as intended. If the project has no
source freshness yet, pair this with `configure-dbt-source-freshness` and say so in the handoff.
