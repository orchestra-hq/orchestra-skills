# Snowflake question log

Every question answered by the `ask-snowflake-question` skill is appended here by
`scripts/log_question.py`, newest at the bottom. The condensed version lives in the
**Known questions → guidepaths** table in `SKILL.md` — read that first; read this
when you need the full SQL or the reasoning behind a caveat.

---

## 2026-10-22 — Which tables can I query in Snowflake, and how big are they?

**Route:** `SNOWFLAKE_WORKING.information_schema.tables` ordered by `row_count desc`, then `information_schema.columns` for the shortlist's shape.

**Answer:** Largest are `PUBLIC.CUSTOMERS` and its clone `PROD_CLEAN.CUSTOMER_CLONE` at 100M rows / 3.6 GB each. The practical demo set is `PUBLIC_AGGREGATED.SNOWFLAKE_ORDERS_SUMMARY` (26,099), `PUBLIC.SNOWPLOW_EVENTS_NORMALIZED` (1,903), `PUBLIC.PAGE_EVENTS_1` (1,722), `PUBLIC_CLEAN.SNOWFLAKE_ORDERS_CLEAN` (1,000) and `PUBLIC.MARKETING_CALENDAR` (365).

**Caveat:** `row_count` is cached metadata and lags recent loads; it is 0 for views. The same logical table is duplicated across `PUBLIC`, `PUBLIC_289`, `PUBLIC_PROD` and `PUBLIC_AGGREGATED` — pick deliberately.

```sql
select table_schema, table_name, row_count, bytes, last_altered::date as last_altered
from SNOWFLAKE_WORKING.information_schema.tables
where table_type = 'BASE TABLE' and row_count > 0
order by row_count desc
limit 30;
```

---

## 2026-10-22 — Is `PUBLIC_CLEAN.SNOWFLAKE_ORDERS_CLEAN` safe to report revenue from?

**Route:** Null/range profile over every column of `PUBLIC_CLEAN.SNOWFLAKE_ORDERS_CLEAN`.

**Answer:** No. Of 1,000 rows: `SOLD_DATE` is 100% NULL, `SHIP_DATE` 75.3% NULL, `QUANTITY` 73.9% NULL, `COST` 26.7% NULL. Only `ITEM_SK_ID` and `ORDER_NUMBER` are fully populated. The summed cost of 57,162 covers barely three-quarters of the rows.

**Caveat:** The `_CLEAN` suffix is doing no work here — treat schema naming as a hint, never as a guarantee. Always profile before quoting a number.

```sql
select count(*) n,
       count(sold_date) sold_date_nn,
       count(ship_date) ship_date_nn,
       count(cost)      cost_nn,
       count(quantity)  quantity_nn,
       count(item_sk_id) item_nn
from SNOWFLAKE_WORKING.PUBLIC_CLEAN.SNOWFLAKE_ORDERS_CLEAN;
```

---

## 2026-10-22 — Does anything in this account hold PII?

**Route:** `information_schema.columns` scanned for name/email/birth patterns, then a `SAMPLE (0.01)` populate-rate check on `PUBLIC.CUSTOMERS`.

**Answer:** Yes. 🚩 `PUBLIC.CUSTOMERS` (100M rows) holds `C_FIRST_NAME`, `C_LAST_NAME`, `C_EMAIL_ADDRESS` and `C_BIRTH_DAY/MONTH/YEAR/COUNTRY`. A 0.01% sample of 9,961 rows found 9,605 emails, 9,593 names and 9,583 birth years populated — roughly 96M unmasked identities, readable by `ORCHESTRA_ROLE`. `PROD_CLEAN.CUSTOMER_CLONE` duplicates it. `PUBLIC_AGGREGATED.SNOWFLAKE_ORDERS` also declares `FIRST_NAME`, `LAST_NAME` and `EMAIL` in an aggregate layer, currently empty but structurally wrong.

**Caveat:** Aggregate over these columns only. Never select row-level values into an answer or a transcript. Recommend masking policies on `CUSTOMERS` and dropping the PII columns from the aggregated model.

```sql
select count(*) n,
       count(c_email_address) emails,
       count(c_first_name)    names,
       count(c_birth_year)    birth_years
from SNOWFLAKE_WORKING.PUBLIC.CUSTOMERS sample (0.01);
```
