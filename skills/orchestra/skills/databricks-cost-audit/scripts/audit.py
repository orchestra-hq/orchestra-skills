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
