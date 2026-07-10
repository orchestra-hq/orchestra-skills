---
name: merge-duplicate-pipelines
description: >
  Finds Orchestra pipelines that are really the same process duplicated — across
  environments (`_prod`/`_staging`/`_dev`/`-uat` naming, or Orchestra's native Environments)
  or conceptually (same task graph copy-pasted per customer/region/business-unit under
  unrelated names) — then drafts one consolidated pipeline using Environment overlays,
  `${{ ENV.* }}`, inputs, conditionals, or a MetaEngine matrix instead of the duplication.
  Use when the user wants to "consolidate", "merge", "dedupe", or "unify" pipelines, asks
  "why do I have three copies of this pipeline", or wants to act on an account-health-check
  finding about one-pipeline-per-environment, duplicated tasks, or hardcoded environment
  values. Also trigger when handed an existing account-review report flagging those. Always
  shows evidence and a drafted YAML before touching anything, and asks per duplicate set
  whether to report, create/PR the unified pipeline, or also pause the originals — never
  merges, deletes, or pauses without that go-ahead.
---

# Merge Duplicate Pipelines

Find pipelines in an Orchestra workspace that are the same process duplicated — across
environments or conceptually — and consolidate each duplicate set into one pipeline with
the right parameterisation in place of the copy-paste. Detection is read-only; anything
that changes a pipeline requires an explicit choice from the user for that specific set.

## References

- `../../references/orchestra/mcp/tools-quick-ref.md` — MCP tool names and arguments.
- `../../references/orchestra/pipeline/yaml-authoring.md` — schema and variable syntax
  (`${{ ENV.* }}`, `${{ inputs.* }}`, `${{ MATRIX.* }}`, conditions).
- `references/detection-and-patterns.md` — **read this before drafting anything.** The
  similarity heuristic in full, the ENV-LABELED vs CONCEPTUAL classification, and
  before/after YAML for each consolidation pattern.
- `../account-health-check/references/best-practices-checklist.md` checks **1.1**
  (one pipeline per process, not per environment), **1.3** (MetaEngine instead of
  duplicated tasks/pipelines), **1.9** (inputs/env vars/conditionals over duplication), and
  **2.1** (don't run one pipeline per environment) — this skill is the fix for those
  findings.

## Workflow

### Step 0 — Fresh detection, or acting on an existing report?

If the user hands you an existing account-review report, or pastes findings that name
checks 1.1/1.3/1.9/2.1, read it for the pipelines it already flagged and skip straight to
**Step 3** with those as your starting candidate set — no need to re-scan the account.
Otherwise start at Step 1.

### Step 1 — Access and scope

Same access pattern as `account-health-check`: use the Orchestra MCP if connected
(`list_pipelines`, `get_pipeline`); otherwise fall back to the REST API with
`$ORCHESTRA_API_KEY` (`https://app.getorchestra.io/api/engine/public`). If neither is
available, point the user at the MCP setup docs and stop.

Tell the user which workspace you're scanning and confirm scope: full account, or a named
subset. For large workspaces, default to the **live + Git-backed set** (every unpaused,
recently-run pipeline plus every Git-backed one) for the same reason `account-health-check`
does — reading every definition has a real cost — and say what you skipped.

### Step 2 — Gather pipeline data

1. `list_pipelines` for the inventory: name, alias, `storageProvider`, `paused`,
   `numTasks`, schedule. Parse `schedule`/`sensors`/`webhook` out of their JSON-encoded
   string form before using them (see the trap noted in `account-health-check`).
2. `get_pipeline` (or the REST fallback) for the full definition of every in-scope
   pipeline. This is what the similarity signatures in Step 3 are built from — there's no
   cheaper source, so this is the expensive step; that's why scope matters.
3. If connected, `list_environments`/`get_environment` to see whether the account already
   has Orchestra Environments configured. This changes the framing of a finding: "you
   haven't set up Environments yet" vs. "you have Environments, but this pipeline isn't
   using them."

### Step 3 — Detect candidate duplicate sets

Run both passes from `references/detection-and-patterns.md` and union the results:

- **Naming pass** — strip environment-like tokens from name/alias and group exact/near
  matches. Cheap, high-precision, catches the obvious case.
- **Structural pass** — for pipelines the naming pass didn't group, compare task-graph
  signatures (integration + job, ignoring IDs/names/param values) with a similarity score.
  **This pass is explicitly tolerant of partial differences** — a pipeline that's a subset
  or superset of another (an extra QA step in staging, an extra notify step in prod) still
  counts as a strong candidate; note the delta rather than requiring an exact match. See
  the thresholds in the reference file — don't force a merge on a weak/ambiguous match,
  surface it and ask instead.

For every candidate set, classify it **ENV-LABELED** or **CONCEPTUAL** per the reference
file — this determines which pattern you draft next.

### Step 4 — Draft the consolidated pipeline per set

Per the classification:

- **ENV-LABELED** → Pattern A (Environment overlay). Replace hardcoded env-specific values
  with `${{ ENV.VAR }}` using the same variable name across every variant. Tasks present in
  only some variants become their own task group gated with `condition` (Pattern B). Name
  the environments in the draft (schedule `environment:` pins, any `ENVIRONMENT_NAME`
  reference) using the **real** names/IDs from Step 2's `list_environments` call whenever
  that succeeded — don't guess a name like `prod`/`staging` when the real one was
  available. Only fall back to a naming-pattern guess when Environments couldn't be
  reached, and flag it explicitly as unconfirmed.
- **CONCEPTUAL** → Pattern C (MetaEngine matrix) if the differing dimension is enumerable
  (customers, regions); otherwise pipeline inputs + a Pattern-B conditional group for the
  handful of variant-specific steps.
- Carry forward every task that exists in any member of the set. Don't silently drop a step
  that only some variants have — gate it, and call out the gating explicitly in the report
  so the user can confirm the condition matches real intent rather than a guess.
- Validate the draft: `orchestra-cli validate <path>` if available, else MCP
  `validate_pipeline`.

### Step 5 — Present and ask before doing anything

Detection and drafting are read-only up to this point. For each candidate set, show:

1. The member pipelines and the similarity evidence (score, which tasks matched, which
   differed and where they ended up in the draft).
2. The drafted unified YAML (or a diff against the largest member).
3. Any manual prerequisites (environment variables to register, secrets to re-enter in the
   UI, Environments that don't exist yet).

Then **ask the user which action to take for that specific set** — there is no default:

1. **Report only** — write the draft to a file, make no pipeline changes.
2. **Create/PR the unified pipeline, leave originals running** — validate on a branch (or a
   draft Orchestra-backed pipeline), but don't touch the duplicates.
3. **Do the above, and also pause the originals** once the new pipeline validates — pause
   only, never delete.
4. **Skip this set.**
5. **Also set up the missing Environments/variables** — only offer this when Step 2 found
   a real gap (an Environment that doesn't exist, or a variable this draft needs that isn't
   registered anywhere yet). Creating a brand-new Environment is comparatively safe; adding
   a variable to one that already exists is not (it's a full-value-set replace, not a
   merge) — see `references/detection-and-patterns.md` §7 for exactly when each is safe to
   do versus when to leave it as a manual UI step instead.

Every set gets its own answer; don't assume the same choice applies to all of them. Option
5 is additive to whichever of 1–4 was chosen, not a replacement for it.

### Step 6 — Execute the chosen action

The unified pipeline is always a **new, additional** pipeline — never one of the original
duplicates rewritten in place. That keeps "create the consolidation" and "retire the
originals" as two separable, individually-approved actions rather than one irreversible step:

- **Git-backed**: new branch, new YAML file, open a PR, validate with a branch run
  (`start_pipeline` with `branch=...`) — same gate as `triage-orchestra-pipeline`. Nothing
  merges to main until the user approves the PR, and the original duplicate files are
  untouched by this PR.
- **Orchestra-backed** (`storageProvider: ORCHESTRA`): `create_pipeline` for the new unified
  pipeline. Do not call `update_pipeline`/`migrate_pipeline` on any of the *original*
  duplicate pipelines here — those tools are only used in the pausing step below, and only
  to flip `paused`, never to rewrite a definition. (Aside: if `create_pipeline` or a later
  `update_pipeline` call 422s on `storage_provider` with `extra_forbidden`, that's a known
  Orchestra MCP quirk — retry the equivalent call via `migrate_pipeline` instead, which
  omits that field.)
- **Pausing originals** (only if the user chose option 3, and only after the new pipeline
  has validated): pause via `update_pipeline`/`migrate_pipeline` — a `paused: true` toggle
  on the existing duplicate, nothing else in its definition changes. Never delete a
  pipeline — that's not offered as an option for a reason.

### Step 7 — Report

Write (or append to) `orchestra-pipeline-consolidation.md`: one section per candidate set
with the evidence, classification, action taken or deferred, links to the PR/pipeline, and
any outstanding manual steps. Chat summary: how many sets found, what was done per set,
what's still pending on the user.

## Notes

- Never delete a pipeline, under any option.
- Cite the specific checklist item in the report: 1.1/2.1 for environment-suffix
  duplication, 1.3 for enumerable duplication that should be a matrix, 1.9 for hardcoded
  values that should be `${{ ENV.* }}`/`${{ inputs.* }}`.
- A weak or ambiguous structural match usually means two pipelines that look similar but do
  genuinely different things. Don't force a merge to hit a number — surface the comparison,
  say what's uncertain, and let the user decide whether it's really a duplicate.
