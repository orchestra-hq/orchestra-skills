# Snowflake table — RETAIL.DWH.DIM_PRODUCTS (dimension)

| Column      | Type         | Nullable | Notes                         |
|-------------|--------------|----------|-------------------------------|
| PRODUCT_SK  | NUMBER       | NO       | Surrogate primary key         |
| PRODUCT_ID  | VARCHAR      | NO       | Natural/business key          |
| LIST_PRICE  | NUMBER(10,2) | YES      | Catalogue price, USD          |
| LAUNCH_DATE | DATE         | YES      | Date the product launched     |
| CATEGORY    | VARCHAR      | YES      | Product category              |

~120K rows. Prices should never be negative and launch dates should be realistic
(nobody launched a product in the year 1900 or 2099).
