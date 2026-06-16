# dbt source freshness — schema reference

This is the warehouse-agnostic shape of source freshness. For *how the freshness signal is
computed* on a specific warehouse — and whether you can skip `loaded_at_field` entirely — read
the matching `warehouses/*.md` file. Get the warehouse part right first; it is the part most
often wrong when guessed.

## What freshness does

dbt records, per source table, when the newest row landed (`max_loaded_at`) and compares it to
your thresholds. Orchestra reads this to answer "does this source have new data?" — the input to
state-aware orchestration. A stale source means its downstream models can be skipped.

## Where it goes, and the version trap

Field **placement moved across dbt versions**. Check the project's dbt version
(`require-dbt-version` in `dbt_project.yml`, or `dbt --version`) before editing, and match what
the project already does rather than forcing a form.

- **dbt < 1.9** — `freshness` and `loaded_at_field` sit at the source/table **root** level.
- **dbt 1.9+** — `freshness` lives under a `config:` block.
- **dbt 1.10+** — `loaded_at_field` also moves under `config:`; `loaded_at_query` is added.

Both forms still parse in current dbt, but author the canonical `config:` form for 1.9+. If the
file already uses root-level freshness and the project is pre-1.9, stay consistent with it.

## Canonical form (dbt 1.9+/1.10+)

```yaml
sources:
  - name: jaffle_shop
    database: raw            # optional; defaults to target database
    schema: jaffle_shop      # optional; defaults to source name
    config:
      freshness:
        warn_after:  { count: 12, period: hour }
        error_after: { count: 24, period: hour }
        filter: "_etl_loaded_at >= date_sub(current_date(), interval 3 day)"  # optional
      loaded_at_field: _etl_loaded_at   # OR loaded_at_query — never both
    tables:
      - name: orders
        identifier: api_orders          # optional; real table name if it differs from `name`
        config:
          freshness:                    # table-level overrides source-level
            warn_after:  { count: 6,  period: hour }
            error_after: { count: 12, period: hour }
      - name: customers                 # inherits source-level freshness
      - name: product_skus
        config:
          freshness: null               # explicitly disable freshness for this table
```

## Field reference

| Field | Notes |
|-------|-------|
| `freshness.warn_after` | `{ count: <int>, period: minute\|hour\|day }`. Optional; set independently of `error_after`. |
| `freshness.error_after` | `{ count: <int>, period: minute\|hour\|day }`. Optional. |
| `freshness.filter` | Optional SQL predicate to narrow the freshness query — soft-delete flags (`_fivetran_deleted = false`) or a partition bound on large tables. Big cost saver. |
| `freshness: null` | Disables freshness for a table that would otherwise inherit it. |
| `loaded_at_field` | A timestamp column **or** SQL expression dbt uses to find the newest row. Mutually exclusive with `loaded_at_query`. |
| `loaded_at_query` | (1.10+) Custom SQL returning the max-loaded timestamp. Use for high-frequency tables where a `max()` scan is expensive. |

## Choosing how freshness is computed

1. **`loaded_at_field`** → a query finds `max(<field>)`. Works on every warehouse — the safe
   default for Orchestra SAO.
2. **`loaded_at_query`** → you supply the SQL. Best for very large/high-frequency tables.
3. **Omit both** → metadata inference. **Under Orchestra SAO this only works on Databricks**
   (`DESCRIBE HISTORY`). On Snowflake, BigQuery, MotherDuck/DuckDB and others there is no Orchestra
   fallback, so omitting both leaves SAO without a reliable freshness signal — provide an explicit
   field instead. This is narrower than dbt's own metadata support; see the warehouse matrix in
   `README.md` and the per-warehouse `warehouses/*.md` files.

## Timezone correctness

dbt compares against UTC. If your timestamp column is not UTC, freshness will be miscalculated.

- Cast non-timestamps: `loaded_at_field: "completed_date::timestamp"`.
- Convert local → UTC inside the field, e.g.
  `loaded_at_field: "convert_timezone('Australia/Sydney', 'UTC', created_at_local)"`.

## How to pick thresholds

Base `warn_after` / `error_after` on the source's real load cadence plus headroom — a table
loaded hourly might `warn_after: 2 hours`, `error_after: 6 hours`. When you don't know the
cadence, ask or leave a clearly-marked placeholder rather than guessing tight values that will
false-alarm. Explain the reasoning in your handoff so the user can tune it.

## Verifying (without running it for them)

The user can confirm config with:

```bash
dbt source freshness                 # all sources -> target/sources.json
dbt source freshness --select "source:jaffle_shop.orders"
```

Each entry reports `max_loaded_at`, `snapshotted_at`, and a `state` of `pass`/`warn`/`error`.
Tell them what a healthy result looks like rather than executing it yourself.
