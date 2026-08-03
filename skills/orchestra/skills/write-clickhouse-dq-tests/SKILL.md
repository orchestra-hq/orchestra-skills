---
name: write-clickhouse-dq-tests
description: Profile ClickHouse data, design data-quality tests appropriate to what each column actually is, then build and deploy a ClickHouse DQ testing pipeline to Orchestra.
---

Goal: inspect real ClickHouse data, **design tests that fit what each column means** (not a
generic null check on everything), deploy them as an Orchestra pipeline, run it, and report
what's actually wrong. A test that **fails** because the data is bad is the skill working
correctly — do **not** tune thresholds until everything is green.

Flow: **profile → design tests → write pipeline YAML → branch (or create pipeline if no git) →
register → run → report.**

## Read first

- `../../references/orchestra/dq-tests/clickhouse.md` — ClickHouse profiling SQL, the test
  catalogue in ClickHouse SQL, the pipeline YAML, and ClickHouse-specific error causes (including
  its beta status).
- `../../references/orchestra/dq-tests/workflow.md` — the engine-agnostic rest of the workflow:
  thresholds, the matrix/gating pattern, branching, registering, triggering, and how to interpret
  results. Applies unchanged to ClickHouse.

## Workflow

1. Profile the data and design tests per `clickhouse.md` §1–2.
2. Write the pipeline YAML per `clickhouse.md` §3, following the gating pattern and threshold
   rules in `workflow.md`.
3. Branch the repo (or create the pipeline if there's no git), register, trigger, poll, and
   report — all per `workflow.md`, using the ClickHouse-specific error causes and qualified-name
   format from `clickhouse.md` §4 when interpreting results.
