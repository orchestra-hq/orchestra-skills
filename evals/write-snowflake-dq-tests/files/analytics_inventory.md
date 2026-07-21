# Snowflake inventory — ANALYTICS database, PUBLIC schema

Two tables. `FCT_ORDERS` is a fact, `DIM_CUSTOMERS` is a dimension.

## ANALYTICS.PUBLIC.FCT_ORDERS  (fact)

| Column        | Type          | Nullable | Notes                          |
|---------------|---------------|----------|--------------------------------|
| ORDER_ID      | NUMBER        | NO       | Primary key, surrogate         |
| CUSTOMER_ID   | NUMBER        | NO       | FK -> DIM_CUSTOMERS            |
| ORDER_TS      | TIMESTAMP_NTZ | NO       | When the order was placed      |
| ORDER_TOTAL   | NUMBER(12,2)  | YES      | Order amount in USD            |
| QUANTITY      | NUMBER        | YES      | Units ordered                  |
| STATUS        | VARCHAR       | YES      | placed / shipped / cancelled   |

Roughly 4.2M rows, loaded continuously throughout the day.

## ANALYTICS.PUBLIC.DIM_CUSTOMERS  (dimension)

| Column      | Type          | Nullable | Notes                       |
|-------------|---------------|----------|-----------------------------|
| CUSTOMER_ID | NUMBER        | NO       | Primary key                 |
| EMAIL       | VARCHAR       | YES      | Customer email              |
| COUNTRY     | VARCHAR       | YES      | ISO country code            |
| CREATED_AT  | TIMESTAMP_NTZ | NO       | When the customer signed up |

Roughly 380K rows, slowly changing.
