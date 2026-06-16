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
   actually consumed).
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
   `databricks`, `duckdb`/MotherDuck) or ask. The warehouse decides whether you can omit
   `loaded_at_field` or must supply one. This is the single most important decision, and it is
   **narrower than dbt's own metadata support** — judge it by Orchestra SAO's matrix, not dbt's:
   - **Databricks** — the *only* warehouse where Orchestra infers freshness from metadata
     (`DESCRIBE HISTORY`). You may omit `loaded_at_field`; use an explicit field only when you
     need "fresh" to strictly mean new rows.
   - **Snowflake** — **explicit `loaded_at_field`/`loaded_at_query` required** (no Orchestra
     fallback; `LAST_ALTERED` is not used by SAO and over-reports anyway).
   - **BigQuery** — not in Orchestra's fallback table → **explicit field required** (dbt's
     `TABLE_STORAGE` metadata is not used by SAO). On large partitioned tables add a partition
     `filter` to keep the query cheap.
   - **MotherDuck/DuckDB** — metadata freshness **not supported**; an explicit `loaded_at_field`
     (or `loaded_at_query`) is **required**. If you can't find a load-timestamp column, ask which
     column marks load time — do not omit it.

   In short: on everything except Databricks, give an explicit field.

2. **Check the dbt version.** From `require-dbt-version` in `dbt_project.yml` or `dbt --version`.
   1.9+ → put `freshness` under `config:`; 1.10+ → `loaded_at_field` under `config:` too. If the
   project already uses an older root-level form, stay consistent with it. (See the reference.)

3. **Find the sources.** Locate existing `sources:` YAML (often `models/**/_sources.yml` or
   `models/**/src_*.yml`). If sources aren't defined yet, that's a prerequisite — define them or
   tell the user. Read a neighbouring source file to match the project's naming and layout.

4. **Author freshness.** Add `warn_after`/`error_after` based on each source's real load cadence
   plus headroom (see the reference for picking thresholds). Add the warehouse-appropriate
   `loaded_at_field`/`loaded_at_query`. Add a `filter` for soft-deletes or partition pruning where
   it helps cost. Don't invent tight thresholds you can't justify — leave a marked placeholder and
   explain it if cadence is unknown.

5. **Enable SAO on the Orchestra task.** Find the dbt Core task
   (`integration: DBT_CORE`, `integration_job: DBT_CORE_EXECUTE`) and set
   `use_state_orchestration: true`. Follow `orchestra-task.md` for the Git-backed (edit YAML +
   commit) vs Orchestra-backed (validate + `update_pipeline`, falling back to `migrate_pipeline`
   on a 422) distinction. If it's already enabled, note that and don't re-apply.

6. **Hand off.** Report: files changed, the warehouse choice and why, thresholds (and any
   placeholders to tune), whether SAO was newly enabled, and how to verify (next step).

## Verifying (don't run it for them)

Tell the user how to confirm, rather than executing:

```bash
dbt source freshness                                  # -> target/sources.json
dbt source freshness --select "source:<name>.<table>"
```

A healthy result shows `state: pass` with a recent `max_loaded_at`. On the next Orchestra run with
SAO enabled, models below a stale source are skipped.

## Guardrails

- Write config only — never run `dbt`, never `start_pipeline`.
- Under Orchestra SAO, only **Databricks** can omit `loaded_at_field` (metadata inference). On
  Snowflake, BigQuery, MotherDuck/DuckDB and others, an explicit `loaded_at_field`/`loaded_at_query`
  is required — don't leave it off.
- Match the project's existing dbt-version form and file conventions; don't reformat unrelated YAML.
- Don't commit secrets; warehouse creds stay in the Orchestra dbt connection / env vars.
- `use_state_orchestration` is SAO — not Slim CI. Don't conflate them.
