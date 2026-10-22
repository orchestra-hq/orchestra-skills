---
name: ask-snowflake-question
description: Answer a natural-language question about data in Snowflake, end to end — pick the right table, write and run safe read-only SQL, sanity-check the result for data-quality traps, and report the answer with its caveats. Then log the question and the route taken back into this skill by opening a pull request, so the next person gets a shortcut. Use whenever someone asks a data question that Snowflake can answer ("how many orders last month", "which countries drive traffic", "what's our average order value", "is this table complete"), or asks to explore, profile or query a Snowflake table.
---

# Ask a question of data in Snowflake

Turn a plain-English question into a trustworthy answer, and leave the trail behind
for the next person.

Two halves, both required:

1. **Answer** the question — route, query, verify, report.
2. **Learn** — append the question and the route you took to the question log and
   open a PR, so the route becomes a guidepath.

Never skip part 2. A skill that doesn't record what it learned is a skill that
answers the same question from scratch forever.

---

## 0. Connect

Credentials arrive as environment variables shaped
`SNOWFLAKE__<CONNECTION_ID>__<FIELD>`. Discover the connection rather than
hardcoding it:

```bash
env | grep -o '^SNOWFLAKE__[A-Z_0-9]*__SNOWFLAKE_ACCOUNT'
```

Use `scripts/sfq.py` for every query. It reads the credentials itself, so no secret
ever appears in a command line, a log, or this transcript.

```bash
python3 scripts/sfq.py "select current_warehouse(), current_role()"
```

If `snowflake-connector-python` is missing: `pip install --user snowflake-connector-python`,
then make sure `~/.local/lib/python3.*/site-packages` is on `PYTHONPATH` — the
script handles this, but a bare `python3 -c "import snowflake"` will not.

### Hard rules

- **Read-only.** `SELECT`, `SHOW`, `DESCRIBE`, `EXPLAIN` only. Never `INSERT`,
  `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `COPY`,
  `GRANT`. If the user wants a write, stop and say so — that is a pipeline's job,
  not a question's.
- **Bound every scan.** Always `LIMIT`. On tables over ~1M rows profile with
  `SAMPLE (0.01)` first and only go full-scan once the query shape is proven.
  The warehouse is shared; a careless cross join is someone else's incident.
- **Never print a credential**, and never echo the environment variable's value.

---

## 1. Route the question

Check the guidepaths table below **first**. If the question matches a logged one,
start from that route instead of rediscovering it.

If it's new, discover:

```bash
# which schemas exist
python3 scripts/sfq.py "show schemas in database <DB>"

# candidate tables, biggest and freshest first
python3 scripts/sfq.py "
select table_schema, table_name, row_count, bytes, last_altered::date
from <DB>.information_schema.tables
where table_type='BASE TABLE' and row_count > 0
order by row_count desc limit 30"

# columns for the shortlist
python3 scripts/sfq.py "
select table_schema||'.'||table_name tbl, column_name, data_type
from <DB>.information_schema.columns
where table_name in ('A','B') order by tbl, ordinal_position"
```

Routing heuristics:

- Prefer a `_CLEAN` / `_AGGREGATED` / marts table over a raw landing table — **but
  verify it, don't trust the name** (see §3).
- Prefer the table with the most recent `LAST_ALTERED`.
- Where several schemas hold the same table name, they are usually dev/PR clones.
  Pick the one the production pipeline writes; if unsure, ask.
- State which table you chose and why, before you show numbers.

---

## 2. Query

Write the smallest SQL that answers the question. Then:

- Return the grain the user asked for, not a raw dump.
- Round money, and name the unit.
- If the answer is a single number, also return the row count it came from, so the
  reader can judge it.

---

## 3. Sanity-check before you report

An answer computed off broken data is worse than no answer. Always run a null and
range profile on the columns you used:

```bash
python3 scripts/sfq.py "
select count(*) n,
       count(<col>) as <col>_non_null,
       min(<date_col>)::date mn, max(<date_col>)::date mx,
       sum(case when <num_col> < 0 then 1 else 0 end) negatives
from <DB>.<SCHEMA>.<TABLE>"
```

Flag and report, in the answer itself:

- a column that is **100% NULL** — the aggregation or load is broken
- null rates above ~5% on a column you aggregated
- `min(date) = max(date)` across many rows — a collapsed date aggregation
- negative quantities or costs, future-dated timestamps, ship-before-order
- row counts that differ wildly between two schemas holding "the same" table

If the check invalidates the answer, say so plainly and give the caveat more
prominence than the number.

### PII — stop and escalate

If a table exposes personal data — names, email addresses, dates of birth, phone
numbers, addresses, government IDs — **do not select those columns into the
answer**, and report it to the user immediately as a flag, with the table, the
columns, and whether a masking policy is applied:

```bash
python3 scripts/sfq.py "
select * from table(<DB>.information_schema.policy_references(
  ref_entity_name=>'<DB>.<SCHEMA>.<TABLE>', ref_entity_domain=>'TABLE'))"
```

Aggregate counts over PII columns are fine (`count(email)`). Row-level values are
not. The same applies to PII columns found in an *aggregated* or *marts* layer,
where they are almost always a modelling mistake worth raising even if currently
empty.

---

## 4. Report

Lead with the answer. Then, in order:

1. The number or table, at the grain asked for.
2. The table(s) and SQL used — so it can be re-run.
3. Data-quality caveats found in §3, if any.
4. PII flags, if any.

Keep it short. Link anything linkable.

---

## 5. Log the question and open a PR — required

Every answered question updates this skill. Run:

```bash
python3 scripts/log_question.py \
  --question "What was total wholesale cost by customer?" \
  --route "SNOWFLAKE_WORKING.PUBLIC_AGGREGATED.SNOWFLAKE_ORDERS_SUMMARY → sum(total_wholesale_cost) group by bill_customer_sk_id" \
  --sql "select bill_customer_sk_id, sum(total_wholesale_cost) ..." \
  --caveat "first_order_date = last_order_date for all rows; no time series possible"
```

The script:

- appends a dated row to `QUESTION_LOG.md`
- adds a one-line entry to the **Known questions → guidepaths** table in this
  `SKILL.md`
- commits both to a new branch and opens a PR against the default branch

It needs `GIT_TOKEN` in the environment and talks to the GitHub REST API with
`curl`/`urllib` — no `gh` CLI required.

Tell the user the PR was opened and link it. If the PR fails to open, say so —
do not silently drop the log.

---

## Known questions → guidepaths

Grown by `log_question.py`. Check here before routing a new question.

| Date | Question | Route | Caveat |
|---|---|---|---|
| 2026-10-22 | Which tables can I query, and how big are they? | `information_schema.tables` ordered by `row_count desc`, joined to `information_schema.columns` for shape | `row_count` is metadata and can lag; it is 0 for views |
| 2026-10-22 | What is total wholesale cost per customer? | `PUBLIC_AGGREGATED.SNOWFLAKE_ORDERS_SUMMARY` → `sum(total_wholesale_cost) group by bill_customer_sk_id` | All rows share `first_order_date = last_order_date = 2018-11-23`; the date rollup is collapsed, so no trend is possible |
| 2026-10-22 | How many orders / what did we sell? | `PUBLIC_CLEAN.SNOWFLAKE_ORDERS_CLEAN` — **use with care** | `SOLD_DATE` is 100% NULL, `QUANTITY` 73.9% NULL, `COST` 26.7% NULL despite the `_CLEAN` schema name. Do not quote revenue from this table |
| 2026-10-22 | Where does our web traffic come from? | `PUBLIC.PAGE_EVENTS_1` → group by `GEO_COUNTRY`, count distinct `DOMAIN_SESSIONID` | Only ~1.7k events across 2 days (13–14 Sep 2026); too small to trend |
| 2026-10-22 | Anything about customers | `PUBLIC.CUSTOMERS` (100M rows) — sample before scanning | 🚩 **PII**: `C_FIRST_NAME`, `C_LAST_NAME`, `C_EMAIL_ADDRESS`, `C_BIRTH_*` are populated and unmasked. Aggregate only; never select rows. `PROD_CLEAN.CUSTOMER_CLONE` is a duplicate of the same data |
