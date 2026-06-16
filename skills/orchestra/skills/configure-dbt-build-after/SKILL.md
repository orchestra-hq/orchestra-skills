---
name: configure-dbt-build-after
description: Configure dbt model build_after for Orchestra state-aware orchestration — author the config.freshness.build_after block (count, period, updates_on) on dbt models so Orchestra rebuilds a model only after a minimum SLA window AND when its upstream data is fresh, then ensure use_state_orchestration is enabled on the Orchestra dbt task. Use when asked to set up build_after, configure per-model rebuild SLAs, gate model rebuilds on upstream freshness, stop unnecessary dbt rebuilds, or set up state-aware orchestration in Orchestra. Trigger on phrases like "configure build_after", "add build_after", "only rebuild when upstream is fresh", "per-model SLA", "updates_on any/all", or "stop rebuilding models that haven't changed" in a dbt or Orchestra context. build_after is warehouse-agnostic (same config for Snowflake, BigQuery, Databricks, MotherDuck) but depends on source freshness being configured — the source/freshness-signal half is the separate configure-dbt-source-freshness skill.
---

# Configure dbt `build_after`

Author the per-model `build_after` config so Orchestra rebuilds a model only when **both** its
SLA window has elapsed **and** its upstream data is fresh. This is the model-side half of
state-aware orchestration (SAO); the source-side half is source freshness (see the
`configure-dbt-source-freshness` skill). This skill **writes config only** — it does not run dbt
or trigger pipelines.

Unlike freshness, `build_after` is **warehouse-agnostic** — the same config works on Snowflake,
BigQuery, Databricks, and MotherDuck. The only warehouse nuance lives upstream in the freshness
signal it consumes.

## When to use

- User wants per-model rebuild SLAs, or to stop rebuilding models when nothing upstream changed.
- User is setting up Orchestra SAO and needs the model-side gating.
- Files like a model's YAML `config:` block or `dbt_project.yml` `models:` are in play.

## What "done" looks like

1. `config.freshness.build_after` (`count`, `period`, optional `updates_on`) is set on the target
   models, in the model YAML or `dbt_project.yml`, matching project conventions.
2. `use_state_orchestration: true` is set on the Orchestra dbt Core task.
3. Source freshness is confirmed present upstream (or flagged as a required companion step).
4. A handoff explains the SLA values chosen, the `updates_on` choice, and how to verify.

## Read first

- `../../references/orchestra/dbt-sao/build-after.md` — `build_after` schema and how to pick
  `count`/`period`/`updates_on`.
- `../../references/orchestra/dbt-sao/orchestra-task.md` — enabling SAO on the task.
- `../../references/orchestra/dbt-sao/source-freshness.md` — only if you also need to add the
  upstream freshness `build_after` depends on.

## Workflow

1. **Confirm upstream freshness exists.** `build_after` gates on "is upstream fresh?", which is
   meaningless without source freshness configured. Check the project's `sources:` YAML. If
   freshness is missing, say so and pair this with `configure-dbt-source-freshness` — don't author
   `build_after` against a signal that doesn't exist.

2. **Identify the target models.** Which models get an SLA? Usually marts / exposed models the
   user cares about refreshing on a cadence. Read a neighbouring model's config to match how the
   project configures models (inline `config:` vs `dbt_project.yml`).

3. **Settle the SLA (`count`/`period`) — ask first, don't guess.** The SLA is a business decision,
   and the user often already knows it. **Prompt the user before doing anything else:** do they
   have a target SLA per model (or a marts-wide default) in mind, or would they like you to derive
   one from warehouse usage? Two paths (see `build-after.md` for queries and detail):
   - **B — user-defined (expect this first):** take the SLA the user gives you.
   - **A — derive from warehouse usage:** only if the user asks for it *and* your client can run
     read-only warehouse queries — estimate how often each model is consumed (or how often its
     upstreams refresh) from query/access history, then **show the user the number + the evidence
     to confirm or override**. Read-only only — never mutate the warehouse, and don't run the query
     without the user opting in.
   Never invent a number; if the user has no SLA and doesn't want the usage path, leave a
   clearly-marked placeholder and explain the trade-off.

4. **Author `build_after`.** Set `count` + `period` to the agreed SLA (e.g. hourly → `count: 1,
   period: hour`). Choose `updates_on` from the model's DAG:
   - `all` — wait until *every* upstream is fresh (joins where a partial refresh would mislead).
   - `any` (default) — rebuild as soon as *any* upstream has new data.

5. **Enable SAO on the Orchestra task.** Find the dbt Core task (`integration: DBT_CORE`,
   `integration_job: DBT_CORE_EXECUTE`) and set `use_state_orchestration: true`, following
   `orchestra-task.md` for the Git-backed vs Orchestra-backed path. If already enabled, note it.

6. **Hand off.** Report: models changed, SLA values + how they were chosen (usage-derived vs
   user-defined) and `updates_on` rationale, whether upstream freshness was present or still
   needed, whether SAO was newly enabled, and how to verify.

## Verifying (don't run it for them)

Explain rather than execute: on the next Orchestra run with SAO enabled, a model with
`build_after` is skipped until its window elapses *and* upstream is fresh; otherwise it builds.
The user can inspect SAO decisions by setting `ORCHESTRA_DBT_DEBUG=true` on the task.

## Guardrails

- Write config only for the pipeline/repo — never run `dbt`, never `start_pipeline`, never mutate
  the warehouse. You may run **read-only** usage/metadata queries to estimate SLAs *only* if the
  user opts in and your client can query the warehouse; otherwise ask the user for the SLAs.
- Don't author `build_after` without upstream source freshness — flag it as a dependency.
- `count`/`period` are required; `updates_on` defaults to `any` — only set it when `all` is meant.
- Match the project's config location (model YAML vs `dbt_project.yml`); don't reformat unrelated YAML.
- `use_state_orchestration` is SAO — not Slim CI. Don't conflate them.
