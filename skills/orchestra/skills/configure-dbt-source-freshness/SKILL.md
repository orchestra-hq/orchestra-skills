---
name: configure-dbt-source-freshness
description: Configure dbt source freshness for Orchestra state-aware orchestration — author warn_after/error_after thresholds and loaded_at_field/loaded_at_query in a dbt project's sources YAML, getting the warehouse details right for Snowflake, BigQuery, Databricks, or MotherDuck/DuckDB, then enable use_state_orchestration on the Orchestra dbt task. Use when asked to set up dbt source freshness, configure freshness checks, detect stale sources, set up state-aware orchestration in Orchestra, or make Orchestra skip downstream models when upstream data hasn't changed. Trigger on phrases like "add source freshness", "configure freshness", "set up state aware orchestration", "skip models when sources are stale", "loaded_at_field", or "warn_after/error_after" in a dbt or Orchestra context. This is the source/freshness-signal half of state-aware orchestration; configuring per-model rebuild SLAs (build_after) is the separate configure-dbt-build-after skill.
---

# Configure dbt source freshness

Author dbt **source freshness** so Orchestra can tell which sources have new data and skip
downstream models when they don't. This is one half of state-aware orchestration (SAO); the other
is `build_after` (see the `configure-dbt-build-after` skill). This skill **writes config only** —
it does not run dbt or trigger pipelines. It explains how to verify instead.

## When to use

- User wants dbt source freshness configured, or stale-source detection.
- User is setting up Orchestra state-aware orchestration and needs the freshness signal.
- Files like `models/staging/_sources.yml`, `sources.yml`, or a dbt `sources:` block are in play.

## What "done" looks like

1. Freshness (`warn_after`/`error_after`, and an explicit `loaded_at_field`/`loaded_at_query`
   where the warehouse needs one) is added to the dbt sources YAML, correct for the warehouse.
2. `use_state_orchestration: true` is set on the Orchestra dbt Core task (so the config is
   actually consumed). No `dbt source freshness` command is added to the pipeline — once SAO is on,
   Orchestra runs the freshness check itself. This skill only authors the config.
3. A handoff explains what changed, the warehouse-specific choice made, how to verify, and any
   placeholders the user must fill.

## Read first

Load these before editing — the warehouse file is the part most often wrong if guessed:

- `../../references/orchestra/dbt-sao/source-freshness.md` — freshness schema + the dbt-version
  placement trap (`config:` block in 1.9+, `loaded_at_field` in 1.10+).
- `../../references/orchestra/dbt-sao/warehouses/<warehouse>.md` — for the detected warehouse.
- `../../references/orchestra/dbt-sao/orchestra-task.md` — enabling SAO on the task.

## Workflow

1. **Detect the warehouse.** Read `profiles.yml` (the `type:` — `snowflake`, `bigquery`,
   `databricks`, `duckdb`/MotherDuck, `redshift`, `fabric`, `postgres`) or ask. The warehouse
   decides how freshness can be computed, and this is **narrower than dbt's own metadata support**
   — judge it by Orchestra SAO's matrix, not dbt's. Read the matching `warehouses/*.md`
   (`other.md` for anything unlisted).

2. **Infer the freshness signal — actively, per source.** Default to *figuring it out*, not
   asking. For each source table, work down this order and use the first that applies; only leave
   freshness unset if the user told you to, or if you genuinely can't locate any usable signal:
   1. **Find a real load-timestamp column** → `loaded_at_field`. Look first at the columns the
      source already declares in YAML, then — if your client can run read-only warehouse queries —
      list the table's columns (`information_schema.columns`, `describe table`, etc.) and pick the
      best load/sync timestamp. Strong candidates: `loaded_at`, `_loaded_at`, `_synced_at`,
      `_fivetran_synced`, `_airbyte_emitted_at`, `ingested_at`, `etl_loaded_at`, `dbt_loaded_at`.
      Weaker fallbacks (event time, not load time): `updated_at`, `created_at` — usable, but
      confirm with the user since they can lag the actual load. (Large/partitioned table → add a
      `filter` or a bounded `loaded_at_query` for cost.)
   2. **No load column, but the warehouse exposes simple last-modified metadata** → author a
      **metadata `loaded_at_query`** so dbt reads it cheaply instead of scanning data. Available
      where simple: **Snowflake** (`INFORMATION_SCHEMA … LAST_ALTERED`) and **BigQuery**
      (`__TABLES__.last_modified_time`) — see those warehouse files for the exact query. Confirm the
      view/column is reachable; warn the user it reflects *any* change, not just loads.
   3. **Databricks** → you may omit `loaded_at_field` entirely; Orchestra infers freshness via
      `DESCRIBE HISTORY`.
   4. **Nothing locatable** (MotherDuck/DuckDB, Redshift, Fabric, Postgres, others with no obvious
      column and no simple metadata) → ask the user which column marks load time. Only leave that
      source's freshness unset if they can't say or explicitly want it skipped — and call it out.

   Net: try to populate freshness for every source you can from warehouse metadata/columns; empty
   is the exception (user opt-out or no signal found), not the default.

3. **Check the dbt version.** From `require-dbt-version` in `dbt_project.yml` or `dbt --version`.
   1.9+ → put `freshness` under `config:`; 1.10+ → `loaded_at_field` under `config:` too. If the
   project already uses an older root-level form, stay consistent with it. (See the reference.)

4. **Find the sources.** Locate existing `sources:` YAML (often `models/**/_sources.yml` or
   `models/**/src_*.yml`). If sources aren't defined yet, that's a prerequisite — define them or
   tell the user. Read a neighbouring source file to match the project's naming and layout.

5. **Author freshness.** Add `warn_after`/`error_after` based on each source's real load cadence
   plus headroom (see the reference for picking thresholds). Add the freshness signal chosen in
   step 2 (`loaded_at_field`, a metadata `loaded_at_query`, or — Databricks only — neither). Add a
   `filter` for soft-deletes or partition pruning where it helps cost. Don't invent tight
   thresholds you can't justify — leave a marked placeholder and explain it if cadence is unknown.

6. **Ensure SAO is enabled on the Orchestra task.** `use_state_orchestration: true` is the SAO
   **master switch** — it makes Orchestra consume *all* SAO config (freshness and `build_after`),
   not a freshness-specific setting. Find the dbt Core task (`integration: DBT_CORE`,
   `integration_job: DBT_CORE_EXECUTE`) and make sure it's on. Follow `orchestra-task.md` for the
   Git-backed (edit YAML + commit) vs Orchestra-backed (validate + `update_pipeline`, falling back
   to `migrate_pipeline` on a 422) distinction. If it's already enabled (e.g. `build_after` was set
   up first), just confirm it — don't re-toggle. **Don't touch the task's `commands`** — flipping
   the toggle is all that's needed; the existing `dbt build` is fine. Orchestra runs the freshness
   check for you, so do *not* prepend `dbt source freshness` or change the dbt commands.

7. **Hand off.** Report: files changed, the freshness signal used per source (real column vs
   metadata query) and why, thresholds (and any placeholders to tune), whether SAO was newly
   enabled, and how to verify (next step).

## Verifying (don't run it for them)

Tell the user how to confirm, rather than executing. This is a **local sanity check**, not a
pipeline step — don't add it to the Orchestra dbt task:

```bash
dbt source freshness                                  # -> target/sources.json
dbt source freshness --select "source:<name>.<table>"
```

A healthy result shows `state: pass` with a recent `max_loaded_at`. On the next Orchestra run with
SAO enabled, models below a stale source are skipped.

## Guardrails

- Write config only for the pipeline/repo — never run `dbt`, never `start_pipeline`, never mutate
  the warehouse. You **may** run **read-only** warehouse inspection (list columns, check a
  last-modified metadata view) to infer the freshness signal — that's expected, not a violation.
- Under Orchestra SAO, only **Databricks** can omit `loaded_at_field` (metadata inference). On
  Snowflake, BigQuery, MotherDuck/DuckDB and others, an explicit `loaded_at_field`/`loaded_at_query`
  is required — don't leave it off. Leave a source's freshness unset only on user opt-out or when no
  load column / simple metadata can be located.
- Match the project's existing dbt-version form and file conventions; don't reformat unrelated YAML.
- Don't commit secrets; warehouse creds stay in the Orchestra dbt connection / env vars.
- `use_state_orchestration` is SAO — not Slim CI. Don't conflate them.
