#!/usr/bin/env python3
"""Run a read-only query against the Orchestra Snowflake connection.

Credentials are read from SNOWFLAKE__<CONNECTION_ID>__<FIELD> environment
variables, so no secret ever appears on a command line.

Usage:
    python3 scripts/sfq.py "select current_role()"
    echo "select 1" | python3 scripts/sfq.py
    python3 scripts/sfq.py --connection SNOWFLAKE_PROD_80122 "select 1"
"""
import argparse
import glob
import os
import re
import sys

for _p in glob.glob(os.path.expanduser("~/.local/lib/python3.*/site-packages")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import snowflake.connector as sc
except ImportError:
    sys.exit(
        "snowflake-connector-python is not installed.\n"
        "  pip install --user snowflake-connector-python"
    )

WRITE = re.compile(
    r"\b(insert|update|delete|merge|create|drop|alter|truncate|copy|grant|revoke|"
    r"put|remove|undrop|swap|call|execute\s+immediate)\b",
    re.I,
)


def discover_connection():
    ids = sorted(
        {
            m.group(1)
            for k in os.environ
            if (m := re.match(r"^SNOWFLAKE__(.+)__SNOWFLAKE_ACCOUNT$", k))
        }
    )
    if not ids:
        sys.exit("No SNOWFLAKE__*__SNOWFLAKE_ACCOUNT environment variable found.")
    if len(ids) > 1:
        print(f"note: several connections found {ids}; using {ids[0]}", file=sys.stderr)
    return ids[0]


def connect(connection_id=None):
    cid = connection_id or discover_connection()
    def p(field, default=None):
        return os.environ.get(f"SNOWFLAKE__{cid}__{field}", default)
    kwargs = dict(
        account=p("SNOWFLAKE_ACCOUNT"),
        user=p("SNOWFLAKE_USER"),
        password=p("SNOWFLAKE_PASSWORD"),
        role=p("SNOWFLAKE_ROLE"),
        warehouse=p("SNOWFLAKE_WAREHOUSE"),
        database=p("SNOWFLAKE_DATABASE"),
        schema=p("SNOWFLAKE_SCHEMA"),
    )
    return sc.connect(**{k: v for k, v in kwargs.items() if v})


def run(sql, connection_id=None):
    """Execute a read-only query. Returns (columns, rows)."""
    if WRITE.search(sql):
        raise ValueError(
            "Refusing to run: this skill is read-only and the statement looks "
            "like a write or DDL."
        )
    with connect(connection_id) as conn:
        cur = conn.cursor()
        cur.execute(sql)
        return [d[0] for d in cur.description], cur.fetchall()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sql", nargs="?", help="SQL to run; read from stdin if omitted")
    ap.add_argument("--connection", help="connection id, e.g. SNOWFLAKE_PROD_80122")
    ap.add_argument("--tsv", action="store_true", help="tab-separated output")
    args = ap.parse_args()

    sql = args.sql if args.sql else sys.stdin.read()
    if not sql.strip():
        ap.error("no SQL supplied")

    try:
        cols, rows = run(sql, args.connection)
    except ValueError as e:
        sys.exit(str(e))

    sep = "\t" if args.tsv else " | "
    print(sep.join(cols))
    for r in rows:
        print(sep.join("" if v is None else str(v) for v in r))


if __name__ == "__main__":
    main()
