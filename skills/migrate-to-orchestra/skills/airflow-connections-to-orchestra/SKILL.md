---
name: airflow-connections-to-orchestra
description: "Use this skill when converting Airflow code that references credentials via Airflow's connection system: any operator/hook kwarg ending in `_conn_id` (conn_id=, aws_conn_id=, snowflake_conn_id=, ssh_conn_id=, slack_conn_id=, gcp_conn_id=, http_conn_id=), any `BaseHook.get_connection(...)` or `Connection` class usage, any `AIRFLOW_CONN_<NAME>` environment variable, or a Secrets Backend (AWS Secrets Manager / Hashicorp Vault) configured for connections. Also covers distinguishing these from `Variable.get()` / `AIRFLOW_VAR_*`, which are non-secret config, not connections. Must be read before finalising any Orchestra YAML with a connection: field converted from an Airflow source."
---

# Airflow Connections → Orchestra Connections

## Overview

Airflow never puts credentials directly in DAG code. Instead, every operator or hook takes a `conn_id` (or a provider-specific variant like `snowflake_conn_id`, `aws_conn_id`, `ssh_conn_id`, `slack_conn_id`, `gcp_conn_id`) that is a **pointer** to a `Connection` record — stored in the metadata DB, an `AIRFLOW_CONN_*` env var, or an external Secrets Backend. The DAG source almost never contains the real host/user/password; it only contains the `conn_id` string. This skill teaches how to recognize each of Airflow's idioms for expressing that pointer and map it to an Orchestra connection — including the full connection-type table, naming rules, and secrets handling in one place, the way `dagster-connections-to-orchestra` and `prefect-connections-to-orchestra` do for their own orchestrators.

---

## Connection Name Format

```yaml
connection: my_snowflake_12345   # format: descriptive-name_XXXXX (5-digit suffix from UI)
```

The 5-digit suffix is assigned by Orchestra when the connection is created — copy it from the UI; never invent it.

**No `conn_id` referenced?** If the task doesn't actually take a `_conn_id=`/`conn_id=` kwarg or call `BaseHook.get_connection(...)` — pure computation, no external client, no secrets — don't invent a connection name or a fake env var placeholder just to fill the field:

```yaml
connection: null   # no distinct conn_id in the source; Orchestra uses the workspace default for this integration
```

**This extends to task parameters that duplicate connection-level scope, too** — e.g. Power BI's `workspace_id` (from `group_id`), or any other parameter whose value is also stored on the Orchestra connection itself. If the source code just reads the same single value everywhere rather than genuinely varying it per task, leave that parameter `null`/omitted and let the connection's own configured value apply.

For environment-specific connections:

```yaml
connection: ${{ ENV.SNOWFLAKE_CONNECTION_NAME }}
```

Set `SNOWFLAKE_CONNECTION_NAME=my_snowflake_12345` in Orchestra's environment settings.

---

## Airflow Credential Idioms → What They Mean

| Airflow pattern | What it is | Where the real value lives |
|---|---|---|
| `conn_id="powerbi_default"` / `aws_conn_id=` / `snowflake_conn_id=` / `ssh_conn_id=` / `slack_conn_id=` / `gcp_conn_id=` / `http_conn_id=` kwarg on an operator or hook | A pointer to a named `Connection` | Airflow metadata DB (Admin → Connections UI), OR an `AIRFLOW_CONN_*` env var, OR a Secrets Backend |
| `BaseHook.get_connection("my_conn").password` (or `.host`, `.login`, `.extra_dejson`) inside a `PythonOperator`/`@task` | Same pointer, resolved manually in code instead of via a provider hook | Same three sources as above |
| `Connection(conn_id=..., conn_type=..., host=..., login=..., password=...)` constructed and `.add()`'d in code (rare, usually in a setup/bootstrap script, not the DAG itself) | Programmatic connection creation | Whatever this code writes to — still ends up in the metadata DB |
| `AIRFLOW_CONN_MY_DB='postgres://user:pass@host:5432/db'` env var (uppercased conn_id, URI-encoded value) | Connection defined entirely via environment, bypassing the metadata DB | The env var itself — if you can see this in a `.env`/deployment manifest, the real credential IS visible in source and needs care not to leak it into any file you write |
| A Secrets Backend is configured (`AwsSecretsManagerBackend`, `HashicorpVaultBackend`, etc., set in `airflow.cfg` / `secrets.backend`) | Connection lookups resolve through the backend first, falling back to the metadata DB | Entirely outside Airflow — DAG code shows only the `conn_id`, nothing else to extract |

In every one of these cases, the Orchestra-side answer is the same: **create one Orchestra connection per distinct `conn_id`** and reference it by name in the YAML `connection:` field. The only thing that differs is how much information you can recover from source to help a human set up that connection correctly.

---

## conn_id kwarg → Orchestra Connection Type

When `conn_id=` is generic (no provider-specific kwarg name), the operator class itself tells you the integration — e.g. `conn_id="powerbi_default"` on a Power BI refresh operator still maps to Orchestra's Power BI connection type, not a generic HTTP connection.

### Databases

| Airflow kwarg / hook | Typical operator(s) | Orchestra connection type |
|---|---|---|
| `snowflake_conn_id=` | `SnowflakeOperator`, `SnowflakeHook` | **Snowflake** |
| `postgres_conn_id=` | `PostgresOperator`, `PostgresHook` | **Postgres** |
| `databricks_conn_id=` | `DatabricksSubmitRunOperator`, `DatabricksSqlOperator` | **Databricks** |
| `gcp_conn_id=` / `google_cloud_conn_id=` / `bigquery_conn_id=` | `BigQueryOperator`, `BigQueryHook` | **GCP Big Query** |
| `aws_conn_id=` (targeting S3) | `S3Hook`, `S3KeySensor` | **AWS** |
| `azure_data_lake_conn_id=` | `ADLSHook` | **Azure** |
| `mssql_conn_id=` | `MsSqlOperator`, `MsSqlHook` | **SQL Server** |
| `aws_conn_id=` (targeting Redshift) | `RedshiftSQLOperator`, `RedshiftDataOperator` | **AWS Redshift** |
| `conn_id=` against a MotherDuck DSN | custom `SqlSensor`/`PythonOperator` | **MotherDuck** |

### Data Integration

| Airflow kwarg / hook | Typical operator(s) | Orchestra connection type |
|---|---|---|
| `airbyte_conn_id=` pointed at `api.airbyte.com` | `AirbyteTriggerSyncOperator` | **Airbyte Cloud** (see `airbyte-cloud-airflow-to-orchestra`) |
| `airbyte_conn_id=` pointed at a self-hosted host | `AirbyteTriggerSyncOperator` | **Airbyte Server** (see `airbyte-server-airflow-to-orchestra`) |
| `fivetran_conn_id=` | `FivetranOperator`, `FivetranSensor` | **Fivetran** (see `fivetran-airflow-to-orchestra`) |
| `dbt_conn_id=` / SSH+dbt combo / Git repo config on a Cosmos `ProjectConfig` | dbt CLI via `BashOperator`/`SSHOperator`/Cosmos | **dbt Core** (see `dbt-core-airflow-to-orchestra`) |

### Notifications

| Airflow kwarg / hook | Typical operator(s) | Orchestra connection type |
|---|---|---|
| `slack_conn_id=` | `SlackAPIPostOperator`, `SlackWebhookOperator` | **Slack** (see `slack-airflow-to-orchestra`) |
| `conn_id=` on a PagerDuty hook | `PagerdutyEventsHook` | **PagerDuty** |
| `http_conn_id=` on a Teams webhook call | `SimpleHttpOperator` against a Teams incoming webhook | **Microsoft Teams** |
| SMTP settings in `airflow.cfg` / `EmailOperator` | `EmailOperator` | **Email** |

### Infrastructure & Protocol

| Airflow kwarg / hook | Typical operator(s) | Orchestra connection type |
|---|---|---|
| `ssh_conn_id=` | `SSHOperator` | **Linux SSH** (see `airflow-bash-ssh-to-orchestra`) |
| `winrm_conn_id=` | `WinRMOperator` | **Windows SSH** |
| `sftp_conn_id=` | `SFTPOperator`, `SFTPSensor` | **SFTP** |
| `http_conn_id=` | `SimpleHttpOperator`, `HttpSensor` | **HTTP** |
| `conn_id=` (generic, no dedicated Airflow operator for Tableau/Power BI dataflows) | `PowerBIOperator`/hooks, hand-rolled `PythonOperator`/`SimpleHttpOperator` calls | Look up the specific integration from the operator/REST call it wraps — e.g. Tableau → **Tableau Cloud** (see `tableau-airflow-to-orchestra`), Power BI → **Power BI** (see `powerbi-airflow-to-orchestra`) |

---

## Secrets Backend Gotcha

If the Airflow deployment configures a Secrets Backend (AWS Secrets Manager, Hashicorp Vault, GCP Secret Manager) for connections, the DAG code you're converting will show **only** the `conn_id` — there is no metadata-DB row, no `AIRFLOW_CONN_*` env var, nothing else in source to extract. This is expected and does not change the conversion:

- Still create one normal Orchestra connection for that `conn_id`.
- Note in your conversion output that the real credential values must be retrieved from the Secrets Backend (or from whoever administers it) rather than from anything visible in the DAG repo — there is nothing further to grep for.
- Never guess at a host/user/password to fill in a placeholder; leave the Orchestra connection fields for the user to complete from the actual secret.

---

## `Variable` / `AIRFLOW_VAR_*` vs `Connection` / `AIRFLOW_CONN_*`

These look similar (`AIRFLOW_VAR_` vs `AIRFLOW_CONN_` env var prefixes) but map to opposite places in Orchestra:

| Airflow | Nature | Orchestra target |
|---|---|---|
| `Variable.get("target_table")` | Non-secret config (table name, env flag, feature toggle) | `inputs:` |
| `AIRFLOW_VAR_TARGET_TABLE=orders` | Same as above, set via env var instead of the UI | `inputs:` |
| `BaseHook.get_connection("my_conn")` / `conn_id=` kwarg | Credential (host, login, password, token) | Orchestra **connection**, referenced via `connection:` |
| `AIRFLOW_CONN_MY_DB='postgres://user:pass@host/db'` | Same credential, expressed as a URI env var | Orchestra **connection** |

```python
# Airflow — Variable is config, not a secret
target_table = Variable.get("target_table", default_var="orders")

# Airflow — Connection is a credential
hook = SnowflakeHook(snowflake_conn_id="snowflake_prod")
```

```yaml
# Orchestra
inputs:
  target_table:
    type: string
    default: orders

pipeline:
  stage-load:
    tasks:
      load-data:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        connection: snowflake_prod_12345   # from snowflake_conn_id="snowflake_prod"
        parameters:
          statement: 'INSERT INTO ${{ inputs.target_table }} SELECT * FROM staging'
```

If a `Variable` value happens to look secret-shaped (an API key someone stashed as a Variable instead of a Connection), flag it — Airflow Variables are **not encrypted by default** unless the key name matches a configured "sensitive" pattern, so treat it with the same caution as a Prefect `Variable.get()` (see `prefect-secrets-to-orchestra` for the parallel case in another orchestrator).

---

## Conversion Checklist

- [ ] Grep the DAG source for every `_conn_id=` kwarg, `BaseHook.get_connection(`, and `Connection(` usage
- [ ] Grep the deployment/env files for `AIRFLOW_CONN_*` (connections) separately from `AIRFLOW_VAR_*` (config)
- [ ] For each distinct `conn_id`, identify the operator/hook it's passed to and look up the Orchestra connection type (table above)
- [ ] Check whether a Secrets Backend is configured (`airflow.cfg` `[secrets] backend`) — if so, note that no further credential detail can be extracted from source
- [ ] Create the Orchestra connection (Settings → Connections) and record its `name_XXXXX` suffix
- [ ] Replace every Airflow `conn_id="..."` reference with the matching Orchestra `connection: name_XXXXX` in the YAML
- [ ] Route `Variable.get()` / `AIRFLOW_VAR_*` values to `inputs:`, never to a connection
- [ ] Never write a real credential value (from an `AIRFLOW_CONN_*` URI or anywhere else) into the Orchestra YAML or any file — connections hold secrets in the Orchestra UI only

---

## Gotchas

- **One `conn_id` can be reused across many tasks/DAGs** — map it to a single Orchestra connection, don't create a duplicate per task.
- **`conn_id=` is generic; the operator class disambiguates the type** — the same generic kwarg name is used by Power BI, HTTP, and many community-provider operators, so identify the type from the operator/hook class, not the kwarg name alone.
- **`AIRFLOW_CONN_*` URIs are real credentials in plain sight** — if a deployment manifest or `.env` file has one, treat the value as sensitive; don't echo it back into any generated file, only use it to identify what fields the new Orchestra connection needs.
- **Secrets Backend means nothing to extract** — this is normal, not a blocker; still create the Orchestra connection, just leave the value fields for the user.
- **`Variable` is not a secret store** — even though it's fetched with a `.get()` call that superficially resembles `Secret.load()` in other orchestrators, Airflow Variables map to `inputs:`, not to a connection.
- **dbt-over-SSH still isn't `LINUX_SSH`** — if a `conn_id`/`ssh_conn_id` is feeding a dbt CLI invocation, defer to `dbt-core-airflow-to-orchestra`, not this skill's SSH mapping.

## References

- Airflow connections concepts: https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/connections.html
- Airflow secrets backends: https://airflow.apache.org/docs/apache-airflow/stable/security/secrets/secrets-backend/index.html
- Orchestra connections: https://docs.getorchestra.io/docs/core-concepts/connections
- Orchestra environments: https://docs.getorchestra.io/docs/core-concepts/environments
