# DQ pipeline workflow (shared across write-*-dq-tests skills)

This covers the parts of building an Orchestra data-quality pipeline that are identical
regardless of warehouse. The warehouse-specific parts — profiling SQL, the test catalogue in that
engine's SQL dialect, the pipeline YAML, and connection details — live in the calling skill's own
per-engine reference file (its "Read first" section names the exact path).

Full flow: **profile → design tests → write pipeline YAML → branch (or create pipeline if no
git) → register → run → report.** Profiling and test design are warehouse-specific (see the
calling skill's per-engine reference); everything below applies unchanged once you have a YAML to
ship.

## Thresholds — and why tests are *meant* to fail sometimes

Each test's SQL returns the violating rows; Orchestra compares the **row count** to:
- `error_threshold_expression` — if met, task is **FAILED**.
- `warn_threshold_expression` — if met (but not error), task is **WARNING**.
- Zero rows → success. Error takes precedence over warn.

So `error_threshold_expression: '> 0'` means "fail if there is even one bad row." For tolerated
noise, raise the error bar and warn earlier, e.g. `warn '> 0'`, `error '> 100'`.

**The point of this skill is to catch bad data, not to produce a green pipeline.** If profiling
shows, say, a timestamp column that's ~70% valid dates with some values in the future, you write
the future-date test with `error '> 0'` so it **fails** and surfaces the problem — you do **not**
widen the year bounds or set the threshold to swallow the future dates. A failing test here is the
correct, desired outcome. When you report, call these out as real data issues, don't hide them.

Set thresholds from the profile: if a column is genuinely allowed some nulls, set the error
threshold to the count you'd consider unacceptable; if zero nulls are acceptable, use `> 0`.

## Gating test groups on upstream loads

Use a `matrix` so one task definition fans out over many table/column targets, and group tests by
kind (one task group per test type). Put failure alerts on the pipeline.

**Every test task group must be gated on the upstream load completing** so the tests actually run.
Set `depends_on` to the load group and add a `condition` that runs the group once the loads have
**completed** — including when a load *failed*, because that's exactly when you most want DQ to
run and catch the damage. Use the "run on any status" trigger plus:
```yaml
condition: ${{ task_groups['airbyte-loads'].all().status == 'COMPLETED' }}
```
(Apply the same pattern when one test group depends on another — reference the upstream group it
waits on. In a standalone, schedule-triggered DQ pipeline with no upstream loads, the first group
has no `depends_on`/`condition`; downstream test groups still chain with the condition.)

## Branch the repo (or create the pipeline if there's no git)

If the Orchestra pipelines are git-backed: create a new feature branch and commit the YAML under
`orchestra/<name>.yml`. If the account is **not** git-backed, recommend connecting git first;
otherwise create the pipeline directly in Orchestra (Orchestra-backed) so the user still has
something runnable, and note it should be moved to git.

## Register the pipeline with Orchestra

Commit and push the branch, then register via the Orchestra MCP:
```
mcp__orchestramcp__import_pipeline(yaml="<contents of orchestra/<name>.yml>")
```
This returns the pipeline UUID — save it. If the alias already exists, this updates it in place.
Validate first with `validate_pipeline` if available.

## Trigger on the branch, poll, and report honestly

```
mcp__orchestramcp__start_pipeline(alias="<pipeline-uuid>", branch="<feature-branch>")
mcp__orchestramcp__get_pipeline_run_status(pipeline_run_id="<run-uuid>")
```
Poll until the status is terminal (not `RUNNING`/`CREATED`). Surface the UI link:
`https://app.getorchestra.io/pipeline-runs/<run-uuid>/lineage`.

**Interpreting results — a failed test is often the right answer:**
- **Test FAILED / WARNING** → the data has the problem you tested for. This is a *finding*, not a
  pipeline bug. Pull the failing task's offending rows (`download_task_run_log` / re-run the
  SELECT) and report the issue: which table/column (the calling skill's per-engine reference has
  the qualified name format), how many bad rows, example values. Do **not** loosen the threshold
  to make it pass.
- **Pipeline error (not a test result)** — a genuine bug in the YAML/SQL, not a data finding — fix
  and re-trigger. The calling skill's per-engine reference lists the common causes for that
  warehouse (typos, quoting, missing engine-specific parameters, connection not set).
- **All green** → either the data is clean or your tests are too lax. Sanity-check against the
  profile from step 1; if you saw issues there, your tests should have caught them.

Final report: the pipeline link, the tests deployed (by table/column/kind), and a clear list of
**data-quality findings** (the failing/warning tests) with counts and examples, separated from any
pipeline fixes you applied.
