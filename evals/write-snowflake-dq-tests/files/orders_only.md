# Snowflake table — SALES.CORE.FCT_TRANSACTIONS (fact)

Single fact table, high volume, append-only.

| Column         | Type          | Nullable | Notes                              |
|----------------|---------------|----------|------------------------------------|
| TRANSACTION_ID | NUMBER        | NO       | Primary key                        |
| ACCOUNT_ID     | NUMBER        | NO       | FK to accounts                     |
| TXN_TS         | TIMESTAMP_NTZ | NO       | Transaction timestamp              |
| AMOUNT         | NUMBER(14,2)  | YES      | Transaction amount, can be refund  |

~50M rows. New rows arrive every few minutes; the table should never go stale.
