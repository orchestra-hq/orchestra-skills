---
name: databricks-cost-audit
description: >-
  Runs a daily, one-off Databricks cost-optimisation audit. Executes 10 checks
  against Databricks system tables (billing, compute, query history, lakeflow),
  writes ranked findings with estimated $ savings to a Delta table, and returns
  a summary highlighting what's new today vs. still-open. Use when the user asks
  to audit Databricks spend, find cost savings, run the daily cost check, or
  review compute/warehouse/storage waste. Triggers: "databricks cost audit",
  "check our databricks spend", "cost optimisation", "run the daily audit".
---

# Requirements:

databricks-sql-connector>=3.0.0

# audit.py
```python
#!/usr/bin/env python3
"""
Daily Databricks cost-optimisation audit.

Connects to a SQL warehouse, runs the checks in checks.py against system tables,
persists ranked findings to a Delta table (idempotent per day), and prints a
JSON + markdown summary that highlights what's new today.

Usage:
    python audit.py                 # run all enabled checks, write findings, print summary
    python audit.py --dry-run       # print the SQL for each check, execute nothing
    python audit.py --no-write      # run checks, return findings, don't persist
    python audit.py --check C05      # run a single check by id prefix

Env: see SKILL.md. Requires databricks-sql-connector.
"""
import argparse
import datetime as dt
import json
import os
import sys
import traceback

from checks import CHECKS, CONFIG

# --------------------------------------------------------------------------- #
# Config from environment
# --------------------------------------------------------------------------- #
CATALOG = os.environ.get("AUDIT_CATALOG", "main")
SCHEMA = os.environ.get("AUDIT_SCHEMA", "cost_audit")
TABLE = os.environ.get("AUDIT_TABLE", "findings")
FQ_TABLE = f"{CATALOG}.{SCHEMA}.{TABLE}"

# Threshold overrides (env wins over checks.CONFIG defaults)
_ENV_TUNING = {
    "AUDIT_LOOKBACK_DAYS": ("lookback", int),
    "AUDIT_MIN_COST_USD": ("min_cost", float),
    "AUDIT_IDLE_CPU_PCT": ("idle_cpu", float),
    "AUDIT_MAX_AUTOTERM_MIN": ("max_autoterm", int),
    "AUDIT_BIG_WORKERS": ("big_workers", int),
    "AUDIT_REPEAT_QUERY_RUNS": ("repeat_runs", int),
}
for env_key, (cfg_key, cast) in _ENV_TUNING.items():
    if env_key in os.environ:
        CONFIG[cfg_key] = cast(os.environ[env_key])

ENABLE_C11 = os.environ.get("AUDIT_ENABLE_C11", "0") == "1"

FINDINGS_COLS = (
    "run_date, check_id, check_name, severity, resource_type, resource_id, "
    "resource_name, owner, workspace_id, detail, est_monthly_saving_usd"
)


def connect():
    """Open a Databricks SQL connection from env vars."""
    try:
        from databricks import sql
    except ImportError:
        sys.exit("databricks-sql-connector is not installed. `pip install databricks-sql-connector`")

    host = os.environ.get("DATABRICKS_HOST")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH")
    token = os.environ.get("DATABRICKS_TOKEN")
    missing = [k for k, v in {
        "DATABRICKS_HOST": host,
        "DATABRICKS_HTTP_PATH": http_path,
        "DATABRICKS_TOKEN": token,
    }.items() if not v]
    if missing:
        sys.exit(f"Missing required env vars: {', '.join(missing)}")

    return sql.connect(
        server_hostname=host.replace("https://", "").rstrip("/"),
        http_path=http_path,
        access_token=token,
    )


def ensure_table(cur):
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {FQ_TABLE} (
          run_date DATE, check_id STRING, check_name STRING, severity STRING,
          resource_type STRING, resource_id STRING, resource_name STRING, owner STRING,
          workspace_id STRING, detail STRING, est_monthly_saving_usd DOUBLE
        ) USING DELTA
    """)


def selected_checks(only):
    checks = [c for c in CHECKS if not c.get("optional") or ENABLE_C11]
    if only:
        checks = [c for c in checks if c["id"].upper().startswith(only.upper())]
    return checks


def run(args):
    checks = selected_checks(args.check)
    if not checks:
        sys.exit(f"No checks matched '{args.check}'")

    if args.dry_run:
        for c in checks:
            print(f"\n-- {c['id']}: {c['name']}\n{c['sql'].format(**CONFIG)}")
        return

    conn = connect()
    cur = conn.cursor()
    ran, skipped = [], []

    try:
        if not args.no_write:
            ensure_table(cur)
            cur.execute(f"DELETE FROM {FQ_TABLE} WHERE run_date = current_date()")

        for c in checks:
            body = c["sql"].format(**CONFIG)
            try:
                if args.no_write:
                    cur.execute(body)  # validates + returns rows, persists nothing
                    n = len(cur.fetchall())
                else:
                    cur.execute(f"INSERT INTO {FQ_TABLE} ({FINDINGS_COLS})\n{body}")
                    n = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else "?"
                ran.append(c["id"])
                print(f"  [ok]   {c['id']}: {n} findings", file=sys.stderr)
            except Exception as e:  # one check failing must not abort the run
                skipped.append({"id": c["id"], "needs": c["needs"], "error": str(e).splitlines()[0]})
                print(f"  [skip] {c['id']}: {str(e).splitlines()[0]}", file=sys.stderr)

        summary = build_summary(cur, ran, skipped) if not args.no_write else {
            "note": "--no-write: findings not persisted, no trend/summary available",
            "checks_ran": ran, "checks_skipped": skipped,
        }
    finally:
        cur.close()
        conn.close()

    emit(summary)


def build_summary(cur, ran, skipped):
    """Refresh the trend view and pull today's ranked findings."""
    cur.execute(f"""
        CREATE OR REPLACE VIEW {FQ_TABLE}_summary AS
        WITH hist AS (
          SELECT check_id, resource_id,
                 min(run_date) AS first_seen, max(run_date) AS last_seen
          FROM {FQ_TABLE}
          GROUP BY check_id, resource_id
        )
        SELECT f.*, h.first_seen, h.last_seen,
               datediff(h.last_seen, h.first_seen) AS days_open,
               (h.first_seen = f.run_date)         AS is_new
        FROM {FQ_TABLE} f
        JOIN hist h ON f.check_id = h.check_id AND f.resource_id = h.resource_id
        WHERE f.run_date = (SELECT max(run_date) FROM {FQ_TABLE})
    """)

    cur.execute(f"""
        SELECT count(*)                              AS n_findings,
               round(sum(coalesce(est_monthly_saving_usd, 0)), 0) AS est_saving,
               count_if(is_new)                      AS n_new,
               round(sum(CASE WHEN is_new THEN coalesce(est_monthly_saving_usd, 0) END), 0) AS new_saving
        FROM {FQ_TABLE}_summary
    """)
    n_findings, est_saving, n_new, new_saving = cur.fetchone()

    cur.execute(f"""
        SELECT check_id, severity, resource_type, resource_name, detail,
               est_monthly_saving_usd, is_new, days_open
        FROM {FQ_TABLE}_summary
        ORDER BY coalesce(est_monthly_saving_usd, 0) DESC, is_new DESC
        LIMIT 15
    """)
    cols = [d[0] for d in cur.description]
    top = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute(f"""
        SELECT check_id, count(*) AS n,
               round(sum(coalesce(est_monthly_saving_usd, 0)), 0) AS saving
        FROM {FQ_TABLE}_summary GROUP BY check_id ORDER BY saving DESC
    """)
    by_check = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

    return {
        "run_date": str(dt.date.today()),
        "table": FQ_TABLE,
        "totals": {
            "findings": n_findings,
            "est_monthly_saving_usd": est_saving,
            "new_today": n_new,
            "new_today_saving_usd": new_saving,
        },
        "by_check": by_check,
        "top_findings": top,
        "checks_ran": ran,
        "checks_skipped": skipped,
    }


def emit(summary):
    """Print JSON (for the agent) + a markdown report (for humans / report file)."""
    print("\n===JSON===")
    print(json.dumps(summary, indent=2, default=str))

    md = render_markdown(summary)
    print("\n===MARKDOWN===")
    print(md)

    try:
        out = os.path.join(os.path.dirname(os.path.dirname(__file__)), f"report_{dt.date.today()}.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\nReport written to {out}", file=sys.stderr)
    except OSError:
        pass


def render_markdown(s):
    if "totals" not in s:
        return f"_{s.get('note', 'no summary')}_"
    t = s["totals"]
    lines = [
        f"# Databricks cost audit — {s['run_date']}",
        "",
        f"**Est. monthly saving identified: ${t['est_monthly_saving_usd']:,.0f}** "
        f"across {t['findings']} open findings.",
        f"**New today: {t['new_today']}** findings (${t['new_today_saving_usd'] or 0:,.0f}).",
        "",
        "## Top opportunities",
        "",
        "| $/mo | New | Age(d) | Sev | Check | Resource | Detail |",
        "|-----:|:---:|-------:|-----|-------|----------|--------|",
    ]
    for f in s["top_findings"]:
        saving = f["est_monthly_saving_usd"]
        lines.append(
            f"| {('$' + format(saving, ',.0f')) if saving is not None else '—'} "
            f"| {'🆕' if f['is_new'] else ''} | {f['days_open']} | {f['severity']} "
            f"| {f['check_id']} | {f['resource_name'] or ''} | {f['detail']} |"
        )
    if s["checks_skipped"]:
        lines += ["", "## Skipped checks", ""]
        for c in s["checks_skipped"]:
            lines.append(f"- **{c['id']}** — {c['error']} (needs: {', '.join(c['needs'])})")
    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Daily Databricks cost audit")
    p.add_argument("--dry-run", action="store_true", help="print SQL, execute nothing")
    p.add_argument("--no-write", action="store_true", help="run checks but don't persist findings")
    p.add_argument("--check", help="run a single check by id prefix, e.g. C05")
    try:
        run(p.parse_args())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
```

# Checks.py

```python
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
```

# System Tables

# System tables used, and how to enable them

All checks read from Databricks **system tables** (Unity Catalog required). The
querying identity needs `SELECT` on the `system` catalog schemas below. Some
schemas are not enabled by default — an admin enables them once per metastore via
the `system.schemas` REST API or the account console.

| Schema | Tables used | Checks | Enabled by default? |
|--------|-------------|--------|---------------------|
| `system.billing` | `usage`, `list_prices` | C01, C02, C04, C07, C09, C10, C11 | Yes |
| `system.compute` | `clusters`, `node_timeline` | C02, C03, C10 | `node_timeline` may need enabling |
| `system.query` | `history` | C05, C06, C07 | Often needs enabling |
| `system.lakeflow` | `job_run_timeline`, `jobs` | C09 | Yes (newer workspaces) |
| `system.access` | `table_lineage` | C08 | Needs enabling; lineage capture must be on |
| `system.information_schema` | `tables` | C08 | Yes |

Enable a schema (admin, once):

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
metastore_id = w.metastores.current().metastore_id
for s in ["compute", "query", "access", "lakeflow"]:
    w.system_schemas.enable(metastore_id=metastore_id, schema_name=s)
```

## Notes & known cloud differences

- **Pricing** joins `system.billing.list_prices` (current row = `price_end_time IS
  NULL`, `currency_code = 'USD'`). Dollar figures are list-price estimates; they do
  not model committed-use / DBU discounts. Treat them as a ranking, not a bill.
- **`usage_metadata`** is a struct; the fields present depend on the workload
  (`cluster_id`, `job_id`, `warehouse_id`, `dlt_pipeline_id`, …).
- **`system.compute.clusters`** is slowly-changing — the scripts take the latest row
  per `cluster_id` via `row_number() … ORDER BY change_time DESC`.
- **Cloud attribute columns** — C10 reads `aws_attributes` / `azure_attributes` /
  `gcp_attributes`. A workspace only has the column for its own cloud; the other
  struct references can raise "column not found". That's expected — the check is
  wrapped and reported as skipped rather than aborting the run. To make it strict,
  edit C10 in `checks.py` to reference only your cloud's attribute struct.
- **`node_timeline`** utilisation is sampled per minute per node; C02 averages
  worker nodes (`driver = false`) over the lookback window.
- **Savings fractions** (e.g. all-purpose→jobs ≈ 0.40, spot ≈ 0.40) live in
  `CONFIG` at the top of `checks.py`. Tune them to your negotiated rates.

## Extending

Add a check by appending a dict to `CHECKS` in `checks.py`. The `sql` must return
the 11 findings columns in order (see the module docstring). Set `optional: True`
to keep it off unless explicitly enabled. Nothing else needs to change — the runner
persists, ranks, and trends it automatically.

-----

# Databricks Cost Audit

A scheduled (daily) cost-optimisation audit. It runs 10 checks against Databricks
**system tables**, accumulates findings in a Delta table so you can see trends,
and returns a dollar-ranked summary.

## What it checks

| ID | Check | Signal |
|----|-------|--------|
| C01 | All-purpose compute running jobs | Interactive DBUs billed against a `job_id` (pay ~2x for job workloads) |
| C02 | Under-utilised clusters | Avg CPU below threshold over the lookback window |
| C03 | Risky cluster config | Auto-termination off/too long, or fixed oversized worker count |
| C04 | Photon review | High-cost non-Photon jobs (candidate) / paying Photon premium on light work |
| C05 | Expensive & repeated queries | Same query hash run many times, high total duration/bytes |
| C06 | Full-table scans | High `read_bytes` with `pruned_files = 0` → missing partitioning/clustering |
| C07 | SQL warehouse right-sizing | High cost but low busy-fraction → oversized or auto-stop too long |
| C08 | Storage sprawl | Managed tables not read in 90 days (candidate for archive/drop) |
| C09 | Job failures burning compute | Repeated failed runs that still billed compute |
| C10 | Instance / pricing leakage | On-demand where spot would do; join to cost for $ impact |

A bonus **C11 tag hygiene** check flags untagged spend (breaks attribution for
everything above). It is included in the script but off by default — enable via
`AUDIT_ENABLE_C11=1`.

## How to run it

1. **Confirm credentials are present** (env vars, see below). If missing, ask the
   user for them — do not guess.
2. Run the audit:
   ```bash
   python scripts/audit.py
   ```
   Useful flags: `--dry-run` (print SQL, run nothing), `--check C05` (single check),
   `--no-write` (compute + return findings but don't persist to the Delta table).
3. The script prints a JSON summary and a markdown report to stdout, and writes
   `report_<date>.md` in the skill directory.
4. **Present the result to the user**: lead with total estimated monthly saving and
   the count of findings that are **new today**, then the top ~10 findings by
   `est_monthly_saving_usd`. Note any checks that were skipped (usually a system
   table not enabled in that workspace) rather than silently dropping them.

## Configuration (environment variables)

Connection (required):
- `DATABRICKS_HOST` — e.g. `adb-1234.5.azuredatabricks.net` (no scheme)
- `DATABRICKS_HTTP_PATH` — SQL warehouse HTTP path, e.g. `/sql/1.0/warehouses/abc123`
- `DATABRICKS_TOKEN` — PAT or OAuth token with access to `system` catalog

Where to store findings (optional, sensible defaults):
- `AUDIT_CATALOG` (default `main`), `AUDIT_SCHEMA` (default `cost_audit`),
  `AUDIT_TABLE` (default `findings`)

Tuning (optional): `AUDIT_LOOKBACK_DAYS` (30), `AUDIT_MIN_COST_USD` (50),
`AUDIT_IDLE_CPU_PCT` (15), `AUDIT_MAX_AUTOTERM_MIN` (60), `AUDIT_BIG_WORKERS` (10),
`AUDIT_REPEAT_QUERY_RUNS` (20), `AUDIT_ENABLE_C11` (0).

## Running it daily

This is designed to be idempotent per day: it deletes any rows already written for
today's `run_date` before inserting, so a re-run replaces the day cleanly. Schedule
it with the `schedule` skill (a cloud routine) or as a Databricks job that shells out
to `audit.py`. The trend view (`<table>_summary`) computes `first_seen` / `days_open`
/ `is_new` from the accumulated history — that's what powers "new today".

## Caveats

- System-table schemas differ slightly by cloud (AWS/Azure/GCP) and evolve over
  time; each check is wrapped so one failure never aborts the run. Skipped checks
  are reported. See `references/system-tables.md` for schema notes and enablement.
- Dollar figures are **estimates** from list prices and heuristic savings fractions —
  they rank opportunities, they are not a bill. Discounts/commitments aren't modelled.
