---
name: review-orchestra-account
description: >
  Audit an Orchestra workspace/account against Orchestra's best practices and produce a
  read-only health report — findings grouped by area, each tagged with severity, evidence,
  and a fix recommendation, written to a markdown file plus a chat summary. Use whenever the
  user wants an "account review", "workspace audit", "health check", "best-practice review",
  "onboarding review", or asks "is my Orchestra set up correctly?", "what should I improve?",
  "are we following best practices?", "review my pipelines", or "audit my workspace". Also
  trigger when the user mentions reviewing pipeline design, environment/promotion setup,
  Git/CI-CD coverage, alerting coverage, connections/secrets hygiene, concurrency, cost, RBAC,
  repeated tasks (MetaEngine), metadata/lineage, auto-fix agents, or hybrid-deployment fit
  across their Orchestra account. This skill only inspects and reports — it never edits
  pipelines or changes settings.
---

# Review Orchestra Account

Audit an Orchestra workspace against the conventions the Orchestra team recommends during
onboarding and account reviews, then deliver a prioritised, evidence-backed report. This is
a **read-only** review: it inspects pipelines, runs, and assets through the Orchestra MCP and
writes a report file — it never mutates pipelines, settings, or runs. If the user wants
something fixed, hand off to `create-orchestra-pipeline` or `fix-orchestra-pipeline`.

The workspace is determined by the API key behind the connected Orchestra MCP server, so the
review covers whatever workspace that key targets. If the user has multiple workspaces, remind
them each one needs its own review (there are no cross-workspace resources).

## References

- `references/best-practices-checklist.md` — **the rubric.** Every check, what "good" looks
  like, the MCP signal that detects a violation, its severity, and the doc link to cite. Read
  this before evaluating — it's the heart of the skill. It has a table of contents; you can read
  the sections relevant to the data you gathered rather than the whole file at once.
- `../../references/orchestra/mcp/tools-quick-ref.md` — Orchestra MCP tool names and arguments.

## Workflow

### Step 0 — Access

Use the Orchestra MCP if connected (`list_pipelines`, `get_pipeline`, `list_task_runs`, etc.). If it
isn't, fall back to the public REST API with `$ORCHESTRA_API_KEY` (often already in the env); for
reading git-backed pipeline YAMLs, `$GITHUB_TOKEN`. If neither MCP nor a key is available, point the
user at the Orchestra MCP setup docs (https://docs.getorchestra.io/docs/mcp) or ask for an API key,
then stop — recommend connecting the MCP regardless, since it also powers the fix/triage skills.

REST base: `https://app.getorchestra.io/api/engine/public` — header
`Authorization: Bearer $ORCHESTRA_API_KEY`.

### Step 1 — Confirm scope and probe capabilities

Tell the user which workspace you'll review (the one the MCP key targets) and ask if they want
the **full** review or a subset of areas (e.g. "just alerting and cost"). Default to full. For
large workspaces (many pipelines), it's fine to offer to sample or focus on production pipelines
first — reading every pipeline definition has a cost, so say so rather than silently truncating.

**Check which Orchestra MCP tools are actually connected before you start.** Tool coverage varies
by server: some deployments expose only the `list_*`/runtime tools, while a single-pipeline read
tool (`get_pipeline`, or similarly named) may be absent. Every definition-level check — alerts,
secrets, concurrency, MetaEngine, `set_outputs`, branching, unique IDs — needs that read tool. If
it isn't present, say so up front: tell the user the review will be **metadata-only**, those checks
will come back **Not assessed**, and the fix is to connect a server that exposes definition reads
(e.g. the remote Orchestra MCP) — don't discover this halfway through and silently degrade.

### Step 2 — Gather data (read-only)

Pull the evidence before judging anything. Batch the `list_*` calls first, then read definitions.

1. **Inventory** — `list_pipelines`. Capture for each pipeline: name, alias, `storageProvider`
   (`GITHUB`/`GITLAB`/etc. = Git-backed; `ORCHESTRA` = UI-only), `paused`, `numTasks`, schedule,
   sensors, webhook, and latest-run metadata. This list alone drives several checks (env-duplication
   by naming, Git-backing, schedule cadence, pause state).
2. **Definitions** — read each pipeline's full definition with the single-pipeline read tool (by
   `alias` or `pipeline_id`). This is where most checks live: alerts, concurrency, MetaEngine/matrix,
   task groups, `${{ ENV. }}` refs vs hardcoded secrets, branching conditions, inputs, triggers/
   sensors, `set_outputs`. **Default scope for large workspaces: the live + Git-backed set** — every
   unpaused, recently-run pipeline plus every Git-backed (`storageProvider != ORCHESTRA`) one, since
   that's what a real audit hinges on. Skip dormant `TEST:`/demo-named pipelines unless asked, and
   **say what you covered vs skipped**. If the read tool is absent (Step 1), skip this and mark the
   definition-level checks Not assessed.
3. **Runtime signals** — `list_pipeline_runs` over the last 7 days (the metadata window). Use this
   to spot concurrency skips, over- or under-scheduling, and noisy failure rates. `list_task_runs`
   /`list_operations` add integration-level detail (e.g. source-tool jobs, dbt models) when a check
   needs it.
4. **Assets** — `list_assets`. Assets with no Orchestra operation in 7+ days are a governance
   signal that work may be running outside Orchestra; confirm with `list_operations` filtered to
   the asset's integration before flagging.
5. **Python compute (opportunistic, for check 7.6)** — if Python tasks are a notable share of the
   workspace, pull recent `PYTHON` task runs (`list_task_runs` / `GET /task_runs?integration=PYTHON&
   page_size=200&time_from=<ISO>&time_to=<ISO>`) and sum `completedAt - startedAt`; note count,
   frequency, and max memory/cpu params. Skip this if Python isn't materially used.

**Two data-shape traps, learned the hard way:**

- **Big `list_*` outputs.** `list_pipelines` and `list_assets` can exceed the tool-output token
  limit on real workspaces and get spilled to a file instead of returned inline. When that happens,
  don't try to read the whole file into context — `jq` it. Probe shape first
  (`jq '.result | type, length'`), then compute the signals you need with `jq`/scripts (counts by
  `storageProvider`, `paused`, cron cadence, staleness) and only surface the aggregates. `list_assets`
  is paginated (`page`/`page_size`/`total`) — note when you've only seen page 1 and treat it as a
  sample.
- **Nested fields arrive as JSON-encoded strings.** In `list_pipelines`, `schedule`, `sensors`,
  `webhook`, and `triggerEvents` come back as *strings* like `"[]"` or `"{\"enabled\":true}"`, not
  parsed arrays/objects. A naive "is it empty?" test counts `"[]"` as non-empty and reports every
  pipeline as scheduled/sensored — a false positive. Parse them first (`jq 'fromjson'`) before
  judging. This is exactly the kind of silent miscount to guard against.

Field names also vary between the YAML form and the stored API form (e.g. `max_active` vs
`maxActive`, `set_outputs` vs `setOutputs`). Match on the concept, not one exact spelling.

### Step 3 — Evaluate against the checklist

Work through `references/best-practices-checklist.md` against the data you gathered. For each
violation, record: the check, the **specific** offending pipeline/task/field (evidence by
location — pipeline → task → field/key name, not vague claims), the severity, and the recommendation
with its doc link. A clean check is worth noting too — the report's value is partly the reassurance
that the basics are covered.

**Never reproduce a secret value.** For credential findings (e.g. checks 4.3/4.4 — a literal secret
in a task param, or a sensitive value in a plain-text env var), cite only the location and the
field/env-var name and state that it holds a literal secret. Do **not** copy the value, or any
fragment of it, into your working notes or the report — not even a masked prefix. The location and
name are enough to fix it; the value must never enter the context or conversation history. The same
applies to any other field whose contents are themselves sensitive.

Be precise and avoid false positives. If you didn't gather the data a check needs (e.g. you sampled
pipelines, or a 7-day window hid something), mark that check **Not assessed** rather than passing or
failing it. A confident "I couldn't see this" beats a guess.

### Step 4 — Note what MCP can't see

Several conventions live in areas the MCP doesn't expose — RBAC roles and groups, IP restrictions,
API-key rotation, the secrets-manager backend, deployment model, and whether source tools
(Fivetran, Airbyte, etc.) are actually paused at the source. These can't be auto-checked. List them
in the report under **Manual verification** as a short checklist the user runs in the UI, rather than
asserting pass/fail. The checklist file marks these items explicitly.

### Step 5 — Score account health

Turn the evaluation into a single **Account health score out of 100** plus per-area sub-scores, so
the user has a headline number to track over time and a leaderboard of where to improve. Compute it
with the **Scoring method** below — it's a weighted pass-rate over the checks you could actually
assess, not a vibe. Report a **coverage** figure alongside it (how many assessable checks you
evaluated) so a metadata-only review is honest about the score being provisional. Never inflate the
score by counting `[MANUAL]` or **Not assessed** checks as passes — they're excluded, not free points.

### Step 6 — Write the report and summarise

Write the report to `orchestra-account-review.md` (in the working directory unless the user names a
path) using the template below, then give a short chat summary: **the health score and band**, the
top 3–5 fixes, and the path to the file.

**Write for a customer who wants to act, not read.** Keep it tight and scannable — the value is the
*ranked fix list*, not exhaustive prose. Concretely:
- Lead with the score and the **Fix first** list — that's the part they'll act on.
- One findings table, **real findings only**, sorted High → Low. Fold evidence into the finding line;
  don't give it its own column. **Never add a row per "Not assessed" check** — collapse all of them
  into the single coverage line at the end.
- Cut anything that doesn't change what the reader does. No methodology dump, no per-area table
  sprawl, no restating the same point in three sections. Aim for a page or so.

## Report structure

Use this template:

```markdown
# Orchestra account review — <workspace name or "current workspace">

_Reviewed <YYYY-MM-DD>. Read-only audit against Orchestra best practices._

## Health score: <NN>/100 — <band emoji + label, e.g. 🟡 Needs attention>

| Area | Score | |
|------|------:|--|
| Pipeline design & structure | <NN>/100 | <bar> |
| Environments & promotion | <NN>/100 | <bar> |
| Version control, Git & CI/CD | <NN>/100 | <bar> |
| Connections & credentials | <NN>/100 | <bar> |
| Alerting & observability | <NN>/100 | <bar> |
| Performance & cost | <NN>/100 | <bar> |

_<a> of <b> checks assessed (<c>%). <Add "Provisional — metadata-only; definition checks need a
server with `get_pipeline`." if applicable.>_

<Render `<bar>` as a 10-cell meter, e.g. `██████████` filled to the score. Drop an area row with no
assessable checks rather than scoring it 0. Pipelines reviewed: <n of m>; note any sampling here.>

## Fix first
1. **<headline fix>** — <impact in a few words; the concrete action>. ([docs](<link>))
2. ...
<The 3–5 highest-impact items. This is the report's payload — make each one do-able.>

## Findings
| Severity | Finding (with evidence) | Fix |
|----------|-------------------------|-----|
| High | <what's wrong + the specific pipeline/task/field; concrete value only if non-sensitive> | <what to do> ([docs](<link>)) |
<Real findings only, sorted High → Low. Skip clean and Not-assessed checks here. For secret/
credential findings, name the location and field only — never put a secret value (or fragment) in
this table.>

## Working well
- <2–4 clean checks worth the reassurance>

## Check manually (not visible to the MCP)
- [ ] <RBAC · IP restrictions · secrets backend · API-key rotation · source-tool pausing>

_Not assessed (<n> checks): <areas, e.g. alerting, secrets, concurrency> — needs pipeline
definitions. <Drop this line entirely if coverage was full.>_
```

## Severity guide

- **High** — security/data-loss risk or a clear reliability hazard: hardcoded secrets or plain-text
  sensitive env vars, production pipelines not Git-backed, no failure alerting on production, no
  concurrency limit where overlapping runs would corrupt data.
- **Medium** — meaningful cost, maintainability, or governance drift: one-pipeline-per-environment,
  repeated tasks that should be a MetaEngine matrix, over-scheduling instead of sensors, alerts
  defined in the UI rather than YAML, webhook alert endpoints with no auth.
- **Low** — polish and best-practice nudges: heartbeat/failure alert-channel split, `LIMIT` on
  SQL sensor checks, stale assets to bring under orchestration, `set_outputs` enabled where unused.

Calibrate to impact and the user's stage — don't bury a High finding under a pile of Lows.

## Scoring method

The health score is a **severity-weighted pass-rate over the checks you actually assessed** — same
inputs as the quick checklist, turned into a number. Compute it deterministically so the same
workspace always scores the same:

1. **Take the assessable checks.** Every non-`[MANUAL]` check in the rubric that you evaluated.
   **Exclude** `[MANUAL]` checks and any you marked **Not assessed** — they're neither numerator nor
   denominator. (`[MANUAL]` checks never count; a check is only assessable if you had the data.)
2. **Weight each by severity:** High = 5, Medium = 3, Low = 1.
3. **Credit each by outcome:** pass (✅) = full weight, partial (⚠️) = half weight, fail (❌) = 0.
   A check fails once if it has any finding of its severity — don't multiply the penalty by the
   number of offending pipelines (the evidence column already conveys breadth).
4. **Score** = round( 100 × Σ(credit) ÷ Σ(weight of assessed checks) ).
5. **Per-area sub-scores:** the same formula scoped to one area's assessed checks. Drop an area with
   no assessable checks rather than scoring it 0.
6. **Coverage** = assessed assessable checks ÷ total assessable checks, as a %. If coverage is low
   (e.g. a metadata-only review where definition checks were all Not assessed), label the score
   **Provisional** — the number reflects only what was visible.

Bands for the headline label:

- **90–100** 🟢 Excellent · **75–89** 🟢 Healthy · **60–74** 🟡 Needs attention ·
  **40–59** 🟠 At risk · **0–39** 🔴 Critical

Keep the score honest: it measures the *assessed* surface, not the whole account. A 95/100 at 40%
coverage means "what I could see looks great, but I couldn't see most of it" — say exactly that.
