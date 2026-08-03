---
name: databricks-cost-drivers
description: >-
  Rank Databricks jobs and pipelines by cost/runtime and surface the biggest
  cost drivers, with trend direction. Use when the user asks what's costing
  the most in Databricks, which jobs got more expensive, or wants a weekly/
  monthly cost review.
---

# Identify Databricks cost drivers

You help data platform teams understand where Databricks spend is going and
whether it's trending up. Use the Orchestra MCP tools (or Orchestra API)
to gather run data — never estimate or guess durations or costs.

## Steps

1. **Scope the review.** If the user doesn't specify a window, default to
   the last 30 days. Use `list_pipeline_runs` to get all runs for pipelines
   that contain Databricks tasks (integration = Databricks / Databricks Jobs
   / Databricks Workflows / Delta Live Tables).
2. **Collect task-level data.** For each run, use the task/operation list to
   pull every Databricks task: duration, cluster type (job cluster vs
   all-purpose), DBU-relevant metadata if present (node type, autoscaling
   min/max, photon on/off, serverless flag), and status.
3. **Compute a cost-proxy score per job.** Where exact DBU $ cost isn't
   available from Orchestra metadata alone, use duration × cluster size as
   a proxy, and flag it clearly as a proxy rather than a billed dollar
   figure. If the agent has a Databricks SQL/system-tables integration
   available (`system.billing.usage`, `system.billing.list_prices`), prefer
   querying that directly for true DBU/$ cost joined on job/run id — this
   gives exact figures instead of a proxy.
4. **Rank and trend.** Sort jobs by total cost/proxy over the window. For
   each of the top 10, compute the trend vs the prior window of the same
   length (up/down/flat, with %).
5. **Flag anomalies separately from drivers.** A job can be a top spender
   without being anomalous (e.g. a large but expected daily job). Call out
   separately any job whose cost/duration jumped materially more than its
   own historical volatility would suggest — that's a candidate for the
   cluster-review or job-optimisation skills, not just a top-N listing.

## Output

A ranked table — **job/pipeline**, **avg cost or cost-proxy**, **% of total
spend**, **trend vs prior period** — for the top 10, followed by 2-3
sentences flagging anything trending up sharply. State clearly whether
figures are exact (from billing system tables) or a duration-based proxy.
Do not recommend fixes here — that's the cluster-review and
job-optimisation skills; just point to which one applies to each flagged job.