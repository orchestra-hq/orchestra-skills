---
name: write-databricks-dq-tests
description: Profile Databricks data, design data-quality tests appropriate to what each column actually is, then build and deploy a Databricks DQ testing pipeline to Orchestra.
---

Goal: inspect real Databricks data, **design tests that fit what each column means** (not a
generic null check on everything), deploy them as an Orchestra pipeline, run it, and report
what's actually wrong. A test that **fails** because the data is bad is the skill working
correctly — do **not** tune thresholds until everything is green.

Flow: **profile → design tests → write pipeline YAML → branch (or create pipeline if no git) →
register → run → report.**

## Read first

- `../../references/orchestra/dq-tests/databricks.md` — Databricks profiling SQL, the test
  catalogue in Databricks SQL, the pipeline YAML, and Databricks-specific error causes.
- `../../references/orchestra/dq-tests/workflow.md` — the engine-agnostic rest of the workflow:
  thresholds, the matrix/gating pattern, branching, registering, triggering, and how to interpret
  results. Applies unchanged to Databricks.

## Workflow

1. Profile the data and design tests per `databricks.md` §1–2.
2. Write the pipeline YAML per `databricks.md` §3, following the gating pattern and threshold
   rules in `workflow.md`.
3. Branch the repo (or create the pipeline if there's no git), register, trigger, poll, and
   report — all per `workflow.md`, using the Databricks-specific error causes and qualified-name
   format from `databricks.md` §4 when interpreting results.
