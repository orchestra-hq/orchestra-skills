"""
Cost-audit checks against Databricks system tables.

Each check is a dict: {id, name, severity, needs, sql}. `sql` is a SELECT that
returns exactly the 11 findings columns, in this order:

    run_date, check_id, check_name, severity, resource_type, resource_id,
    resource_name, owner, workspace_id, detail, est_monthly_saving_usd

audit.py wraps each SELECT in `INSERT INTO <findings> <sql>` (or runs it directly
for --no-write). `needs` lists the system tables the check reads, so the runner can
report *why* a check was skipped when a table isn't enabled in the workspace.

Placeholders in `{braces}` are filled from CONFIG via str.format — the SQL itself
contains no literal braces. Schemas vary by cloud and evolve; validate in-workspace.
"""

# ---------------------------------------------------------------------------
# Tunable thresholds (overridden from env in audit.py)
# ---------------------------------------------------------------------------
CONFIG = {
    "lookback": 30,          # days
    "min_cost": 50,          # USD over lookback window before a resource is worth flagging
    "idle_cpu": 15,          # avg CPU % below this = under-utilised
    "max_autoterm": 60,      # auto-termination minutes above this = flag
    "big_workers": 10,       # fixed (non-autoscaling) worker count at/above this = flag
    "repeat_runs": 20,       # identical query run at least this many times = repeated
    "ap_to_jobs_saving": 0.40,   # ~ fraction saved moving all-purpose -> jobs compute
    "idle_saving": 0.50,         # fraction of an idle cluster's cost assumed recoverable
    "photon_saving": 0.15,       # net illustrative saving from Photon change
    "spot_saving": 0.40,         # typical spot discount vs on-demand
    "wh_idle_saving": 0.50,      # recoverable fraction of an idling warehouse
    "big_bytes": 50 * 1024**3,   # 50 GB single-query scan = "large"
}

# Shared CTE: current USD list prices + priced usage over the lookback window.
# Prepended (as the first WITH item) to every check that needs $ figures.
PRICED = """
prices AS (
  SELECT sku_name, MAX(pricing.default) AS unit_price
  FROM system.billing.list_prices
  WHERE currency_code = 'USD' AND price_end_time IS NULL
  GROUP BY sku_name
),
usage30 AS (
  SELECT
    u.workspace_id,
    u.sku_name,
    u.usage_date,
    u.usage_quantity,
    u.usage_metadata,
    u.custom_tags,
    u.usage_quantity * COALESCE(p.unit_price, 0) AS cost_usd
  FROM system.billing.usage u
  LEFT JOIN prices p ON u.sku_name = p.sku_name
  WHERE u.usage_date >= date_sub(current_date(), {lookback})
)
"""

CHECKS = [
    # -----------------------------------------------------------------------
    {
        "id": "C01_all_purpose_for_jobs",
        "name": "All-purpose compute running scheduled jobs",
        "severity": "high",
        "needs": ["system.billing.usage", "system.billing.list_prices"],
        "sql": """
WITH """ + PRICED + """
SELECT
  current_date()                                        AS run_date,
  'C01_all_purpose_for_jobs'                            AS check_id,
  'All-purpose compute running scheduled jobs'          AS check_name,
  'high'                                                AS severity,
  'cluster'                                             AS resource_type,
  usage_metadata.cluster_id                             AS resource_id,
  usage_metadata.cluster_id                             AS resource_name,
  CAST(NULL AS STRING)                                  AS owner,
  workspace_id                                          AS workspace_id,
  concat('all-purpose DBUs on job_id ', max(usage_metadata.job_id),
         ' cost $', round(sum(cost_usd), 0), ' over {lookback}d')  AS detail,
  round(sum(cost_usd) * {ap_to_jobs_saving}, 2)         AS est_monthly_saving_usd
FROM usage30
WHERE sku_name LIKE '%ALL_PURPOSE%'
  AND usage_metadata.job_id IS NOT NULL
GROUP BY workspace_id, usage_metadata.cluster_id
HAVING sum(cost_usd) > {min_cost}
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C02_idle_clusters",
        "name": "Under-utilised clusters (low CPU)",
        "severity": "high",
        "needs": ["system.billing.usage", "system.compute.node_timeline"],
        "sql": """
WITH """ + PRICED + """,
util AS (
  SELECT cluster_id,
         avg(cpu_user_percent + cpu_system_percent) AS avg_cpu,
         avg(mem_used_percent)                       AS avg_mem
  FROM system.compute.node_timeline
  WHERE start_time >= date_sub(current_date(), {lookback})
    AND driver = false
  GROUP BY cluster_id
),
cost AS (
  SELECT usage_metadata.cluster_id AS cluster_id, workspace_id, sum(cost_usd) AS cost_usd
  FROM usage30
  WHERE usage_metadata.cluster_id IS NOT NULL
  GROUP BY usage_metadata.cluster_id, workspace_id
)
SELECT
  current_date(), 'C02_idle_clusters', 'Under-utilised clusters (low CPU)', 'high',
  'cluster', c.cluster_id, c.cluster_id, CAST(NULL AS STRING), c.workspace_id,
  concat('avg CPU ', round(u.avg_cpu, 1), '%, avg mem ', round(u.avg_mem, 1),
         '%, {lookback}d cost $', round(c.cost_usd, 0)),
  round(c.cost_usd * {idle_saving}, 2)
FROM cost c
JOIN util u ON c.cluster_id = u.cluster_id
WHERE u.avg_cpu < {idle_cpu} AND c.cost_usd > {min_cost}
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C03_cluster_config",
        "name": "Risky cluster config (no auto-term / no autoscale)",
        "severity": "medium",
        "needs": ["system.compute.clusters"],
        "sql": """
WITH latest AS (
  SELECT *, row_number() OVER (PARTITION BY cluster_id ORDER BY change_time DESC) AS rn
  FROM system.compute.clusters
  WHERE delete_time IS NULL
)
SELECT
  current_date(), 'C03_cluster_config',
  'Risky cluster config (no auto-term / no autoscale)', 'medium',
  'cluster', cluster_id, cluster_name, owned_by, workspace_id,
  concat('auto_term=', coalesce(cast(auto_termination_minutes AS string), 'null'),
         ', workers=', coalesce(cast(worker_count AS string), 'null'),
         ', autoscale=', coalesce(cast(min_autoscale_workers AS string), 'off')),
  CAST(NULL AS DOUBLE)
FROM latest
WHERE rn = 1
  AND cluster_source IN ('UI', 'API')
  AND (coalesce(auto_termination_minutes, 0) = 0
       OR auto_termination_minutes > {max_autoterm}
       OR (min_autoscale_workers IS NULL AND coalesce(worker_count, 0) >= {big_workers}))
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C04_photon_review",
        "name": "Photon review (high-cost non-Photon jobs)",
        "severity": "medium",
        "needs": ["system.billing.usage", "system.billing.list_prices"],
        "sql": """
WITH """ + PRICED + """
SELECT
  current_date(), 'C04_photon_review', 'Photon review (high-cost non-Photon jobs)', 'medium',
  'cluster', usage_metadata.cluster_id, usage_metadata.cluster_id,
  CAST(NULL AS STRING), workspace_id,
  concat('non-Photon jobs compute $', round(sum(cost_usd), 0),
         ' over {lookback}d — evaluate Photon for throughput/$'),
  round(sum(cost_usd) * {photon_saving}, 2)
FROM usage30
WHERE sku_name LIKE '%JOBS%'
  AND sku_name NOT LIKE '%PHOTON%'
  AND usage_metadata.cluster_id IS NOT NULL
GROUP BY workspace_id, usage_metadata.cluster_id
HAVING sum(cost_usd) > {min_cost} * 4
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C05_expensive_queries",
        "name": "Expensive and repeated queries",
        "severity": "medium",
        "needs": ["system.query.history"],
        "sql": """
WITH q AS (
  SELECT
    workspace_id,
    sha2(regexp_replace(lower(statement_text), '[0-9]+', 'N'), 256) AS q_hash,
    min(substring(statement_text, 1, 100))     AS q_sample,
    count(*)                                   AS runs,
    round(sum(total_duration_ms) / 1000.0, 0)  AS total_sec,
    round(sum(read_bytes) / 1e12, 3)           AS read_tb
  FROM system.query.history
  WHERE start_time >= date_sub(current_date(), {lookback})
    AND statement_type = 'SELECT'
    AND execution_status = 'FINISHED'
  GROUP BY workspace_id, q_hash
)
SELECT
  current_date(), 'C05_expensive_queries', 'Expensive and repeated queries', 'medium',
  'query', q_hash, q_sample, CAST(NULL AS STRING), workspace_id,
  concat(runs, ' runs, ', total_sec, 's total, ', read_tb, ' TB scanned over {lookback}d'),
  CAST(NULL AS DOUBLE)
FROM q
WHERE runs >= {repeat_runs} AND total_sec > 600
ORDER BY total_sec DESC
LIMIT 50
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C06_full_scans",
        "name": "Full-table scans (no file pruning)",
        "severity": "medium",
        "needs": ["system.query.history"],
        "sql": """
WITH q AS (
  SELECT
    workspace_id,
    sha2(regexp_replace(lower(statement_text), '[0-9]+', 'N'), 256) AS q_hash,
    min(substring(statement_text, 1, 100)) AS q_sample,
    count(*)                               AS runs,
    round(avg(read_bytes) / 1e9, 1)        AS avg_gb,
    sum(read_files)                        AS files_read,
    sum(pruned_files)                      AS files_pruned
  FROM system.query.history
  WHERE start_time >= date_sub(current_date(), {lookback})
    AND read_files > 0
    AND read_bytes > {big_bytes}
  GROUP BY workspace_id, q_hash
)
SELECT
  current_date(), 'C06_full_scans', 'Full-table scans (no file pruning)', 'medium',
  'query', q_hash, q_sample, CAST(NULL AS STRING), workspace_id,
  concat(runs, ' runs, avg ', avg_gb, ' GB/scan, 0 files pruned — partition/liquid-cluster the source'),
  CAST(NULL AS DOUBLE)
FROM q
WHERE files_pruned = 0
ORDER BY avg_gb DESC
LIMIT 50
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C07_warehouse_rightsizing",
        "name": "SQL warehouse right-sizing / auto-stop",
        "severity": "high",
        "needs": ["system.billing.usage", "system.query.history"],
        "sql": """
WITH """ + PRICED + """,
wcost AS (
  SELECT usage_metadata.warehouse_id AS wh, workspace_id, sum(cost_usd) AS cost_usd
  FROM usage30
  WHERE usage_metadata.warehouse_id IS NOT NULL
  GROUP BY usage_metadata.warehouse_id, workspace_id
),
wq AS (
  SELECT compute.warehouse_id AS wh,
         count(*) AS runs,
         sum(total_duration_ms) / 1000.0 AS busy_sec
  FROM system.query.history
  WHERE start_time >= date_sub(current_date(), {lookback})
    AND compute.warehouse_id IS NOT NULL
  GROUP BY compute.warehouse_id
)
SELECT
  current_date(), 'C07_warehouse_rightsizing', 'SQL warehouse right-sizing / auto-stop', 'high',
  'warehouse', c.wh, c.wh, CAST(NULL AS STRING), c.workspace_id,
  concat('$', round(c.cost_usd, 0), ' over {lookback}d, ', coalesce(q.runs, 0), ' queries, busy ',
         round(100.0 * coalesce(q.busy_sec, 0) / ({lookback} * 86400), 1), '% of the window'),
  round(c.cost_usd * (1 - least(1.0, coalesce(q.busy_sec, 0) / ({lookback} * 86400))) * {wh_idle_saving}, 2)
FROM wcost c
LEFT JOIN wq q ON c.wh = q.wh
WHERE c.cost_usd > {min_cost}
  AND coalesce(q.busy_sec, 0) / ({lookback} * 86400) < 0.25
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C08_storage_sprawl",
        "name": "Storage sprawl (tables not queried in 90d)",
        "severity": "low",
        "needs": ["system.information_schema.tables", "system.access.table_lineage"],
        "sql": """
WITH used AS (
  SELECT DISTINCT source_table_full_name AS t
  FROM system.access.table_lineage
  WHERE event_time >= date_sub(current_date(), 90)
    AND source_table_full_name IS NOT NULL
)
SELECT
  current_date(), 'C08_storage_sprawl', 'Storage sprawl (tables not queried in 90d)', 'low',
  'table',
  concat_ws('.', table_catalog, table_schema, table_name),
  concat_ws('.', table_catalog, table_schema, table_name),
  CAST(NULL AS STRING), CAST(NULL AS STRING),
  'managed table with no read in table_lineage for 90d — archive/drop, or VACUUM+OPTIMIZE if kept',
  CAST(NULL AS DOUBLE)
FROM system.information_schema.tables t
WHERE table_type = 'MANAGED'
  AND table_catalog NOT IN ('system', '__databricks_internal')
  AND concat_ws('.', table_catalog, table_schema, table_name) NOT IN (SELECT t FROM used)
LIMIT 200
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C09_job_failures",
        "name": "Job failures burning compute",
        "severity": "medium",
        "needs": ["system.lakeflow.job_run_timeline", "system.billing.usage"],
        "sql": """
WITH """ + PRICED + """,
runs AS (
  SELECT job_id, run_id, workspace_id,
         max(result_state)                                           AS state,
         sum(unix_timestamp(period_end_time) - unix_timestamp(period_start_time)) AS run_sec
  FROM system.lakeflow.job_run_timeline
  WHERE period_start_time >= date_sub(current_date(), {lookback})
  GROUP BY job_id, run_id, workspace_id
),
agg AS (
  SELECT job_id, workspace_id,
         count(*)                                        AS total_runs,
         count_if(state = 'FAILED')                      AS failed_runs,
         sum(CASE WHEN state = 'FAILED' THEN run_sec ELSE 0 END) AS failed_sec,
         sum(run_sec)                                    AS all_sec
  FROM runs
  GROUP BY job_id, workspace_id
),
jcost AS (
  SELECT usage_metadata.job_id AS job_id, sum(cost_usd) AS cost_usd
  FROM usage30
  WHERE usage_metadata.job_id IS NOT NULL
  GROUP BY usage_metadata.job_id
)
SELECT
  current_date(), 'C09_job_failures', 'Job failures burning compute', 'medium',
  'job', cast(a.job_id AS string), coalesce(j.name, cast(a.job_id AS string)),
  CAST(NULL AS STRING), a.workspace_id,
  concat(a.failed_runs, '/', a.total_runs, ' runs failed over {lookback}d, ',
         round(a.failed_sec / 3600.0, 1), ' compute-hours wasted'),
  round(coalesce(c.cost_usd, 0) * a.failed_sec / nullif(a.all_sec, 0), 2)
FROM agg a
LEFT JOIN jcost c ON a.job_id = c.job_id
LEFT JOIN system.lakeflow.jobs j ON a.job_id = j.job_id AND a.workspace_id = j.workspace_id
WHERE a.failed_runs >= 3
""",
    },
    # -----------------------------------------------------------------------
    {
        "id": "C10_pricing_leakage",
        "name": "On-demand where spot would do",
        "severity": "medium",
        "needs": ["system.compute.clusters", "system.billing.usage"],
        "sql": """
WITH """ + PRICED + """,
latest AS (
  SELECT *, row_number() OVER (PARTITION BY cluster_id ORDER BY change_time DESC) AS rn
  FROM system.compute.clusters
  WHERE delete_time IS NULL
),
cost AS (
  SELECT usage_metadata.cluster_id AS cid, workspace_id, sum(cost_usd) AS cost_usd
  FROM usage30
  WHERE usage_metadata.cluster_id IS NOT NULL
  GROUP BY usage_metadata.cluster_id, workspace_id
)
SELECT
  current_date(), 'C10_pricing_leakage', 'On-demand where spot would do', 'medium',
  'cluster', l.cluster_id, l.cluster_name, l.owned_by, co.workspace_id,
  concat('on-demand workers, ', round(co.cost_usd, 0), ' $/{lookback}d — use spot/fleet for fault-tolerant work'),
  round(co.cost_usd * {spot_saving}, 2)
FROM latest l
JOIN cost co ON l.cluster_id = co.cid
WHERE l.rn = 1
  AND co.cost_usd > {min_cost}
  AND upper(coalesce(l.aws_attributes.availability,
                     l.azure_attributes.availability,
                     l.gcp_attributes.availability, '')) LIKE '%ON_DEMAND%'
""",
    },
    # -----------------------------------------------------------------------
    # Bonus: tag hygiene (off by default; enable with AUDIT_ENABLE_C11=1)
    {
        "id": "C11_tag_hygiene",
        "name": "Untagged spend (no cost-centre attribution)",
        "severity": "low",
        "optional": True,
        "needs": ["system.billing.usage", "system.billing.list_prices"],
        "sql": """
WITH """ + PRICED + """
SELECT
  current_date(), 'C11_tag_hygiene', 'Untagged spend (no cost-centre attribution)', 'low',
  coalesce(
    CASE WHEN usage_metadata.warehouse_id IS NOT NULL THEN 'warehouse'
         WHEN usage_metadata.job_id       IS NOT NULL THEN 'job'
         WHEN usage_metadata.cluster_id   IS NOT NULL THEN 'cluster' END, 'other'),
  coalesce(usage_metadata.warehouse_id, cast(usage_metadata.job_id AS string), usage_metadata.cluster_id, 'unknown'),
  coalesce(usage_metadata.warehouse_id, cast(usage_metadata.job_id AS string), usage_metadata.cluster_id, 'unknown'),
  CAST(NULL AS STRING), workspace_id,
  concat('$', round(sum(cost_usd), 0), ' untagged over {lookback}d — add cost_centre/team tag'),
  CAST(NULL AS DOUBLE)
FROM usage30
WHERE NOT (map_contains_key(custom_tags, 'cost_centre') OR map_contains_key(custom_tags, 'team'))
GROUP BY workspace_id,
  coalesce(
    CASE WHEN usage_metadata.warehouse_id IS NOT NULL THEN 'warehouse'
         WHEN usage_metadata.job_id       IS NOT NULL THEN 'job'
         WHEN usage_metadata.cluster_id   IS NOT NULL THEN 'cluster' END, 'other'),
  coalesce(usage_metadata.warehouse_id, cast(usage_metadata.job_id AS string), usage_metadata.cluster_id, 'unknown')
HAVING sum(cost_usd) > {min_cost}
""",
    },
]
