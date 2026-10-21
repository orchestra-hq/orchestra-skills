# Orchestra state-aware orchestration (dbt) references

Shared knowledge for the dbt **state-aware orchestration (SAO)** skills. SAO lets Orchestra
rebuild only the dbt models whose code changed or whose upstream data is actually fresh,
instead of rebuilding the whole DAG on every run.

> **Supported dbt versions.** SAO runs on dbt Core **1.10.x–1.12.x** and on **dbt 2.x**
> (`>=2,<3`). On dbt 2.x the project installs `pip install dbt-orchestra "dbt-oss>=2,<3"`, and
> must **not** have `dbt-core` or adapter packages installed alongside it — check the task's
> dependencies before authoring, since a project carrying both is the likely cause of a 2.x setup
> that never produces freshness results. A project outside that range (dbt Core below 1.10) is
> outside what Orchestra supports: say so rather than authoring config that may not be consumed.
> **The major version also changes where implicit freshness comes from** — see
> [the version split](#the-one-rule-that-decides-everything-per-warehouse) below. See the
> [state management guide](https://docs.getorchestra.io/docs/guides/dbt-core-state-management/guide).

Two things drive that decision, and each has its own skill:

| Component | Where it is configured | Skill |
|-----------|------------------------|-------|
| **Source freshness** — "is there new upstream data?" | dbt project `sources` YAML | `configure-dbt-source-freshness` |
| **`build_after`** — "should this model rebuild yet?" | dbt project model `config.freshness` | `configure-dbt-build-after` |

Both depend on one Orchestra-side switch: `use_state_orchestration: true` on the dbt Core task
(see [orchestra-task.md](orchestra-task.md)). Without it, the dbt config is authored but never
consumed.

## How these compose

The two skills can run on their own or together — with one asymmetry:

- **Source freshness — standalone.** Run `configure-dbt-source-freshness` by itself and you have a
  complete SAO setup: Orchestra skips models below a stale source. It also turns SAO on.
- **`build_after` — independent to add, but dependent on freshness to *work*.** Its "rebuild only
  when upstream is **fresh**" half needs a freshness signal to read. You can author it alone (the
  SLA/time-window part still works), but the freshness-gating part is inert until source freshness
  exists — so `configure-dbt-build-after` checks for freshness first and tells the user to pair it
  with `configure-dbt-source-freshness` if it's missing.
- **Both together — the full picture.** Set up freshness first, then `build_after`.
- **The SAO switch is shared.** `use_state_orchestration` is enabled by *whichever* skill you run
  first; there is no separate "enable SAO" step, and the second skill just confirms it's on (see
  [orchestra-task.md](orchestra-task.md)).

## Files

| File | Purpose |
|------|---------|
| `source-freshness.md` | dbt `freshness` / `loaded_at_field` / `loaded_at_query` schema, version placement, `filter` |
| `build-after.md` | dbt model `config.freshness.build_after` schema (`count`, `period`, `updates_on`) |
| `orchestra-task.md` | Enabling SAO on the Orchestra dbt Core task (Git-backed vs Orchestra-backed) |
| `warehouses/snowflake.md` | Snowflake — explicit field required (`LAST_ALTERED` not used by SAO) |
| `warehouses/bigquery.md` | BigQuery — explicit field required; partition `filter` for cost |
| `warehouses/databricks.md` | Databricks — the one warehouse with metadata inference (`DESCRIBE HISTORY`) |
| `warehouses/motherduck.md` | MotherDuck / DuckDB — not supported; explicit field required |
| `warehouses/redshift.md` | Redshift — explicit field required |
| `warehouses/fabric.md` | Microsoft Fabric (`dbt-fabric`) — explicit field required |
| `warehouses/postgres.md` | PostgreSQL — explicit field required |
| `warehouses/other.md` | Catch-all for unlisted adapters — assume no fallback, explicit field required |

## The one rule that decides everything per warehouse

Source freshness can be computed two ways:

1. **Explicit** — you give dbt a `loaded_at_field` (a timestamp column) or a `loaded_at_query`,
   and a query finds the newest row. Works on every warehouse.
2. **Warehouse-native metadata** — you omit both, and freshness is inferred from the warehouse's
   own table metadata (no data scan). **Which warehouses that covers depends on the dbt major
   version**, so establish the version before deciding (see below).

This is the trap on **dbt Core 1.x**: dbt *itself* can read metadata freshness on several
warehouses (Snowflake `LAST_ALTERED`, BigQuery `TABLE_STORAGE`), but **Orchestra state-aware
orchestration does not use those fallbacks** — it registers its own adapter-specific freshness
query for only a few warehouses, and Databricks is the only one. Per Orchestra's
state-management guide, on dbt Core 1.x, when `loaded_at_field` and `loaded_at_query` are both
omitted:

| Warehouse | Orchestra SAO metadata fallback on dbt Core 1.x? | What to author |
|-----------|----------------------------------|----------------|
| **Databricks** | **Yes** — Orchestra runs `DESCRIBE HISTORY` on the source relation | May omit `loaded_at_field`; metadata inference works |
| **Snowflake** | No fallback, but metadata is queryable | Explicit `loaded_at_field`; **or** a metadata `loaded_at_query` on `INFORMATION_SCHEMA … LAST_ALTERED` when no load column exists |
| **BigQuery** | No fallback, but metadata is queryable | Explicit `loaded_at_field`; **or** a metadata `loaded_at_query` on `__TABLES__.last_modified_time` when no load column exists |
| **MotherDuck / DuckDB** | Not supported, no simple metadata | **Explicit `loaded_at_field`/`loaded_at_query` required** |
| **Redshift** | No fallback, metadata not simple | **Explicit `loaded_at_field`/`loaded_at_query` required** |
| **Microsoft Fabric** | No fallback, metadata not simple | **Explicit required** |
| **PostgreSQL** | No fallback, metadata not simple | **Explicit required** |
| Other adapters (Trino, ClickHouse, Athena, …) | No fallback unless listed above | Explicit; metadata `loaded_at_query` only if the warehouse exposes a simple last-modified view |

"Metadata `loaded_at_query`" = point `loaded_at_query` at the warehouse's own last-modified
metadata so dbt reads it cheaply instead of scanning data — handy when a source has no load
column. It still satisfies SAO's "explicit query required" rule. Caveat: such metadata reflects
*any* change, not just loads, so it can over-report freshness; a real `loaded_at_field` is more
precise.

> Orchestra's own words: "For adapters without a registered fallback, if both `loaded_at`
> settings are missing, Orchestra follows dbt's `FreshnessRunner` behaviour (which may surface as
> warnings or a non-actionable result)." So **on dbt Core 1.x, for everything except Databricks,
> give an explicit `loaded_at_field` (or `loaded_at_query`)** — otherwise SAO has no reliable
> freshness signal.

### On dbt 2.x the implicit path is dbt's own, not Orchestra's

The table above is a dbt Core 1.x rule. On **dbt 2.x**, omitting both `loaded_at_field` and
`loaded_at_query` falls through to **dbt's own metadata freshness** instead of Orchestra's
registered adapter fallbacks — so what works implicitly is whatever that dbt version supports for
the adapter, not Orchestra's one-warehouse list, and the `DESCRIBE HISTORY` path is not what runs
on Databricks either. Two consequences when authoring:

- Don't carry a 1.x "this warehouse has no fallback, so freshness is impossible without a column"
  conclusion onto a 2.x project, and don't promise an adapter works implicitly on 2.x without
  checking dbt's own freshness support for it.
- An **explicit `loaded_at_field` (or `loaded_at_query`) is still the safe default on both major
  versions** — it behaves the same way regardless, so prefer it whenever a load column exists and
  reserve implicit freshness for the cases the version actually supports.

Read the relevant `warehouses/*.md` file before authoring freshness — this is the part most
likely to be wrong if guessed, because it contradicts dbt's general behaviour.

## Official docs

- State management guide: https://docs.getorchestra.io/docs/guides/dbt-core-state-management/guide
- State management tutorial: https://docs.getorchestra.io/docs/guides/dbt-core-state-management/tutorial
- dbt Core execute task params: https://docs.getorchestra.io/docs/integrations/dbt_core/dbt_core_execute
- dbt source freshness: https://docs.getdbt.com/reference/resource-properties/freshness
