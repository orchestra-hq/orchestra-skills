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
  edit C10 in `scripts/checks.py` to reference only your cloud's attribute struct.
- **`node_timeline`** utilisation is sampled per minute per node; C02 averages
  worker nodes (`driver = false`) over the lookback window.
- **Savings fractions** (e.g. all-purpose→jobs ≈ 0.40, spot ≈ 0.40) live in
  `CONFIG` at the top of `scripts/checks.py`. Tune them to your negotiated rates.

## Extending

Add a check by appending a dict to `CHECKS` in `scripts/checks.py`. The `sql` must
return the 11 findings columns in order (see the module docstring). Set
`optional: True` to keep it off unless explicitly enabled. Nothing else needs to
change — the runner persists, ranks, and trends it automatically.
