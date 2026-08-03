# Detecting duplicate pipelines & consolidation patterns

## Contents
1. Naming-pattern grouping
2. Structural similarity scoring
3. Classifying ENV-LABELED vs CONCEPTUAL
4. Pattern A — Environment overlay
5. Pattern B — Conditional task group for partial structural differences
6. Pattern C — MetaEngine matrix for enumerable conceptual duplicates
7. Environments feature setup notes

---

## 1. Naming-pattern grouping

Strip environment-like tokens from each pipeline's `name` and `alias` — case-insensitive,
delimited by `_`, `-`, space, parentheses, or a camelCase boundary: `prod`, `production`,
`staging`, `stage`, `stg`, `dev`, `development`, `uat`, `test`, `qa`, `sandbox`. Two
pipelines whose stripped strings match exactly, or are within edit-distance ~2 of each
other, are a naming-pass candidate pair. This is the cheap, high-precision pass — it catches
the obvious `customer_sync_prod` / `customer_sync_staging` case immediately.

## 2. Structural similarity scoring

Naming alone misses duplicates that were never named consistently (copy-pasted once, then
renamed independently over time, or built for different "environments" that are really just
different customers/teams). Run a structural pass over every pipeline pair not already
grouped by naming:

1. Build a **signature** per pipeline: the multiset of `(integration, integration_job)`
   across every task in `get_pipeline`'s definition. Deliberately ignore task/task-group
   UUIDs, names, and parameter *values* — those are exactly the dimension expected to
   differ between "duplicates."
2. Score two pipelines' signatures with Jaccard overlap: `matched / (matched + onlyA + onlyB)`.
3. Thresholds:
   - **≥ 0.85**, with at most 1–2 tasks only on one side — strong candidate. The
     only-on-one-side tasks are the interesting part; carry them into the draft under
     Pattern B rather than dropping them.
   - **0.6–0.85** — possible candidate. Surface it with the delta, but don't draft a merge
     unprompted; ask the user whether the gap is a real difference (a genuinely extra
     process step) or drift worth consolidating.
   - **< 0.6** — not a candidate. Don't flag it; forcing a merge here usually means gluing
     together two different processes.
4. Use non-task signals as supporting evidence only, never as the primary signal: same
   schedule cadence shape, same alert-destination pattern, overlapping connection
   integrations.

## 3. Classifying ENV-LABELED vs CONCEPTUAL

- **ENV-LABELED** — the naming pass matched, or the names carry an environment token even
  without an exact stripped match (`"Customer Sync - Prod"` vs `"Customer Sync (staging)"`).
  These map naturally onto Orchestra's own Environments concept.
- **CONCEPTUAL** — the structural pass matched but the names carry no environment token at
  all (`"Acme Corp ETL"` vs `"Globex ETL"`, near-identical task graphs, differing only in a
  customer-specific parameter). These usually don't belong in Environments — they're the
  same *process* running for different *inputs*, which is what MetaEngine matrices are for.

Classification determines which pattern below to draft. A set can be both: e.g. three
pipelines that are each an env-labeled pair *and* differ by customer — draft the env
overlay first, then let the customer dimension become a matrix inside the single result.

## 4. Pattern A — Environment overlay (ENV-LABELED sets)

**Before** — `snowflake_sync_prod.yml` and `snowflake_sync_staging.yml`: identical task
graphs, but `warehouse_identifier: PROD_WH` / `STAGING_WH` hardcoded inline, and each has
its own `connection`.

**After** — one pipeline. Replace the hardcoded value with an `${{ ENV.* }}` reference using
the *same* variable name across every environment, and drop the hardcoded `connection` so
Orchestra resolves the environment-scoped connection at run time:

```yaml
parameters:
  warehouse_identifier: ${{ ENV.WAREHOUSE_IDENTIFIER }}
```

Schedules or `start_pipeline` calls pick which environment a given trigger runs against
(the `environment` field), so the two cron schedules that used to point at two separate
pipelines become two schedules on the *one* pipeline, each pinned to its environment.

**Manual step to call out in the report:** `WAREHOUSE_IDENTIFIER` (and any other var you
introduced) needs registering with the right value in each Orchestra Environment before the
schedules switch over. `list_environments`/`get_environment` show what's already there;
`create_environment`/`update_environment` can add the variable *names* if MCP is connected,
but never enter a secret value yourself — point the user at the UI for that.

## 5. Pattern B — Conditional task group for partial structural differences

When one variant has a task the others don't — a QA/data-diff step that only runs in
staging, a Slack notify that only fires in prod — don't drop it and don't force it to run
everywhere. `condition` lives on a **task group**, not an individual task (it applies to
every task inside that group), so isolate the differing task into its own group, wire
`depends_on` the same way it sat in the original flow, and gate the group:

```yaml
  <group-id>:
    tasks:
      <task-id>:
        integration: SLACK
        integration_job: SLACK_SEND_MESSAGE
        # ...
    depends_on:
    - <upstream-group-id>
    condition: ${{ ENV.ENVIRONMENT_NAME == "prod" }}
    name: Notify on completion (prod only)
```

If the account isn't using Environments yet, gate on whatever input the relevant
trigger/schedule already sets instead:

```yaml
condition: ${{ inputs.environment == "staging" }}
```

Say explicitly in the report which tasks got a condition and why — this is the one place a
bad guess causes real harm (silently dropping a step some pipelines actually needed). If
you're not confident the condition captures the right logic, say so and ask rather than
drafting it silently.

## 6. Pattern C — MetaEngine matrix (enumerable CONCEPTUAL duplicates)

When the same task graph repeats for a finite list of things — customers, regions, business
units — rather than for an Orchestra environment, don't force it into an Environments
overlay. Turn the enumerable dimension into a `matrix` block: one task graph, N matrix
values swapping in the per-item parameter, each with a stable `id`:

```yaml
matrix:
  inputs:
    customers:
    - id: acme
      SCHEMA_NAME: acme_prod
    - id: globex
      SCHEMA_NAME: globex_prod
```

Reference the value in task params as `${{ MATRIX.customers['SCHEMA_NAME'] }}`. This is
checklist item 1.3 in `account-health-check` — cite it in the report.

## 7. Environments feature setup notes

- `list_environments` / `get_environment` (MCP) show what's already configured — use them
  to get the **real** environment names and IDs rather than guessing from pipeline naming.
  Prefer the real name in every draft (schedule `environment:` pins, `${{ ENV.* }}`
  references in the report) whenever this call succeeded. Only fall back to a guess
  inferred from the pipeline names (e.g. `prod`/`staging`) when Environments genuinely
  couldn't be reached, and say plainly that it's a guess needing confirmation — don't
  present a guessed name with the same confidence as a looked-up one.
- If the account has **no** Environments set up at all, that's a real prerequisite gap —
  say so plainly in the report. It's fine to *offer* to close it (see below), but it isn't
  something to route around with more pipeline-level conditionals instead.
- `create_environment` and `update_environment` both require actual **values**, not just
  variable names — there's no "declare the name, fill in the value later" call. Their risk
  profiles are very different, so treat them differently:
  - **`create_environment` (an Environment that doesn't exist at all)** is comparatively
    safe to offer, since there's nothing existing to overwrite. The values it needs are
    usually already sitting in the original duplicate pipelines' hardcoded fields (e.g. a
    literal `warehouse_identifier` or `connector_id`) — confirm the mapping with the user,
    exclude anything connection/credential-shaped, and never invent a value that wasn't
    already visible somewhere.
  - **`update_environment` (adding a variable to an *existing* Environment)** replaces the
    entire value set — it does **not** merge. Calling it with only the one new variable
    would silently delete every other variable that environment (and whatever pipelines
    depend on it) currently relies on. If you offer this at all: `get_environment` first to
    read every existing value, add only the new one to that set, and pass any existing
    `integration_credential`-typed value straight through unread rather than re-typing or
    re-deriving it. If that doesn't feel safe for a given environment — e.g. you can't be
    confident you've captured every existing value — leave it as a manual UI step and say
    so, rather than risking a partial `update_environment` call.
- A pipeline can run against different environments from different schedules or
  `start_pipeline` calls — that's the mechanism that replaces "one pipeline per
  environment" with "one pipeline, N environment-pinned triggers."
