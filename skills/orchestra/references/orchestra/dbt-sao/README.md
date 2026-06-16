# Orchestra state-aware orchestration (dbt) references

Shared knowledge for the dbt **state-aware orchestration (SAO)** skills. SAO lets Orchestra
rebuild only the dbt models whose code changed or whose upstream data is actually fresh,
instead of rebuilding the whole DAG on every run.

Two things drive that decision, and each has its own skill:

| Component | Where it is configured | Skill |
|-----------|------------------------|-------|
| **Source freshness** — "is there new upstream data?" | dbt project `sources` YAML | `configure-dbt-source-freshness` |
| **`build_after`** — "should this model rebuild yet?" | dbt project model `config.freshness` | `configure-dbt-build-after` |

Both depend on one Orchestra-side switch: `use_state_orchestration: true` on the dbt Core task
(see [orchestra-task.md](orchestra-task.md)). Without it, the dbt config is authored but never
consumed.

## Files

| File | Purpose |
|------|---------|
| `source-freshness.md` | dbt `freshness` / `loaded_at_field` / `loaded_at_query` schema, version placement, `filter` |
| `build-after.md` | dbt model `config.freshness.build_after` schema (`count`, `period`, `updates_on`) |
| `orchestra-task.md` | Enabling SAO on the Orchestra dbt Core task (Git-backed vs Orchestra-backed) |
| `warehouses/snowflake.md` | Snowflake freshness specifics (`LAST_ALTERED`, profile) |
| `warehouses/bigquery.md` | BigQuery freshness specifics (`TABLE_STORAGE`, batch flag, partition filter) |
| `warehouses/databricks.md` | Databricks freshness specifics (`DESCRIBE HISTORY`, classic vs Fusion) |
| `warehouses/motherduck.md` | MotherDuck / DuckDB — no metadata freshness; explicit field required |

## The one rule that decides everything per warehouse

Source freshness can be computed two ways:

1. **Explicit** — you give dbt a `loaded_at_field` (a timestamp column) or a `loaded_at_query`,
   and a query finds the newest row. Works on every warehouse.
2. **Warehouse-native metadata** — you omit both, and freshness is inferred from the warehouse's
   own table metadata (no data scan). **Under Orchestra SAO this works on Databricks only.**

This is the trap: dbt *itself* can read metadata freshness on several warehouses (Snowflake
`LAST_ALTERED`, BigQuery `TABLE_STORAGE`), but **Orchestra state-aware orchestration does not use
those fallbacks** — it registers an adapter-specific freshness query for only a few warehouses.
Per Orchestra's state-management guide, when `loaded_at_field` and `loaded_at_query` are both
omitted:

| Warehouse | Orchestra SAO metadata fallback? | What to author |
|-----------|----------------------------------|----------------|
| **Databricks** | **Yes** — Orchestra runs `DESCRIBE HISTORY` on the source relation | May omit `loaded_at_field`; metadata inference works |
| **Snowflake** | No Orchestra fallback | **Explicit `loaded_at_field` or `loaded_at_query` required** |
| **MotherDuck / DuckDB** | Not supported | **Explicit `loaded_at_field` or `loaded_at_query` required** |
| **BigQuery** | Not listed → no Orchestra fallback | **Explicit `loaded_at_field` or `loaded_at_query` required** |
| Microsoft Fabric, PostgreSQL | No Orchestra fallback | Explicit required |
| Other adapters | No fallback unless listed above | Explicit; or verify dbt's default for that warehouse |

> Orchestra's own words: "For adapters without a registered fallback, if both `loaded_at`
> settings are missing, Orchestra follows dbt's `FreshnessRunner` behaviour (which may surface as
> warnings or a non-actionable result)." So **for everything except Databricks, give an explicit
> `loaded_at_field` (or `loaded_at_query`)** — otherwise SAO has no reliable freshness signal.

Read the relevant `warehouses/*.md` file before authoring freshness — this is the part most
likely to be wrong if guessed, because it contradicts dbt's general behaviour.

## Official docs

- State management guide: https://docs.getorchestra.io/docs/guides/dbt-core-state-management/guide
- State management tutorial: https://docs.getorchestra.io/docs/guides/dbt-core-state-management/tutorial
- dbt Core execute task params: https://docs.getorchestra.io/docs/integrations/dbt_core/dbt_core_execute
- dbt source freshness: https://docs.getdbt.com/reference/resource-properties/freshness
