---
name: dagster-connections-to-orchestra
description: "Use this skill when converting Dagster code that references resources holding credentials (ConfigurableResource subclasses, EnvVar, integration resources like SnowflakeResource / S3Resource / DbtCliResource, or resources wired into Definitions) to Orchestra. Triggers: any Dagster resource that stores host/login/token/key, any EnvVar used for credentials, or environment-specific resource configuration. Must be read before finalising any Orchestra YAML that contains a connection: field."
---

# Dagster Resources -> Orchestra Connections

## Overview

Dagster stores credentials in **resources** — typically `ConfigurableResource` subclasses (or built-in integration resources like `SnowflakeResource`, `S3Resource`, `DbtCliResource`) wired into `Definitions(resources={...})`, with secret values supplied via `EnvVar`. Orchestra connections serve the same purpose but are configured in the Orchestra UI (Settings -> Connections) and referenced by name in pipeline YAML. This skill maps common Dagster resources to their Orchestra equivalents and covers naming, environment patterns, and secrets.

---

## Connection Name Format

For the Orchestra-side naming format, `connection: null` fallback, task-parameter-scope caveat, and
environment-specific `${{ ENV.VAR }}` pattern, see the shared reference:
[`../../references/connections.md`](../../references/connections.md).

**No resource referenced?** If the `@op`/`@asset` doesn't actually instantiate a credentialed resource — pure computation, no external client, no secrets — don't invent a connection name or a fake env var placeholder just to fill the field. Only set a specific `name_XXXXX` or `${{ ENV.VAR }}` when the source code actually references a distinct resource/credential.

---

## Resource Type Mapping

### Databases

| Dagster resource | Orchestra connection type | Key fields |
|---|---|---|
| `PostgresResource` / `dagster-postgres` | **Postgres** | host, port, database, user, password |
| `SnowflakeResource` (`dagster-snowflake`) | **Snowflake** | account, warehouse, database, role, user, password/key pair |
| `DatabricksClientResource` (`dagster-databricks`) | **Databricks** | host (workspace URL), token |
| `BigQueryResource` (`dagster-gcp`) | **GCP Big Query** | service account JSON |
| `S3Resource` (`dagster-aws`) | **AWS** | access key ID, secret, region |
| `ADLS2Resource` (`dagster-azure`) | **Azure** | tenant, client ID, client secret |
| `MSSQL` via pyodbc | **SQL Server** | host, port, database, user, password |
| `RedshiftClientResource` (`dagster-aws`) | **AWS Redshift** | host, port, database, user, password |
| `MotherDuckResource` (`dagster-motherduck`) | **MotherDuck** | token |

### Data Integration

| Dagster resource | Orchestra connection type | Notes |
|---|---|---|
| `AirbyteCloudResource` | **Airbyte Cloud** | API key |
| `AirbyteResource(host=,port=)` | **Airbyte Server** | host URL + API key |
| `FivetranResource` | **Fivetran** | API key + secret |
| `DbtCliResource` / `DbtProject` | **dbt Core** | Git repo URL + branch + warehouse creds |
| `CensusResource` | **Census** | API token |
| `HightouchResource` | **Hightouch** | API key |
| `HexResource` | **Hex** | API token |

### Notifications

| Dagster resource | Orchestra connection type | Notes |
|---|---|---|
| `SlackResource` | **Slack** | Bot Token (`xoxb-...`) or Incoming Webhook |
| `PagerDutyService` (`dagster-pagerduty`) | **PagerDuty** | integration key |
| `MSTeamsResource` (`dagster-msteams`) | **Microsoft Teams** | Incoming Webhook URL |
| email / SMTP | **Email** | SMTP host, port, login, password |

### Infrastructure & Protocol

| Dagster resource | Orchestra connection type | Notes |
|---|---|---|
| `SSHResource` (`dagster-ssh`) | **Linux SSH** | host, port, username, private key |
| `SSHResource` (Windows OpenSSH) | **Windows SSH** | host, port, username, key/password |
| `SFTPResource` / `sftp_resource` | **SFTP** | host, port, username, key or password |
| `requests` in an `@asset` (HTTP) | **HTTP** | base URL, optional auth headers |
| `TableauCloudWorkspace` | **Tableau Cloud** | server URL, site, PAT |

---

## Secrets Handling

Never hardcode credentials in YAML — see the shared reference for the standard pattern:
[`../../references/connections.md`](../../references/connections.md#secrets-handling).

For secrets fetched at runtime, use `AWS_SECRETS_MANAGER` or `AZURE_KEY_VAULT` as a preceding task that sets an output, then reference it downstream.

---

## Multi-Environment Pattern

See the shared reference for the `${{ ENV.VAR }}` pattern and full task example:
[`../../references/connections.md`](../../references/connections.md#environment-specific-connections). This mirrors how Dagster swaps resources per deployment/environment.

---

## Dagster EnvVar / Config -> Orchestra inputs:

Non-credential config (a table name, an environment flag) supplied via `EnvVar` or a `Config` field should become `inputs:`:

```python
# Dagster
class Cfg(Config):
    target_table: str = "orders"
```

```yaml
# Orchestra
inputs:
  target_table:
    type: string
    default: orders

pipeline:
  stage-001:
    tasks:
      task-001:
        parameters:
          statement: 'SELECT * FROM ${{ inputs.target_table }}'
```

---

## Connection Setup Checklist

- [ ] Identify each Dagster resource and the secret(s) it holds
- [ ] Find the equivalent Orchestra connection type above
- [ ] Create the connection in Orchestra (Settings -> Connections -> Add Connection)
- [ ] Note the full connection name including the 5-digit suffix
- [ ] Replace placeholder `connection: <name>` with the real name
- [ ] For environment-specific resources, set env vars and use `${{ ENV.VAR }}`
- [ ] Never put credentials/tokens in the YAML

---

## Gotchas

- **5-digit suffix is required** — `connection: snowflake_prod` fails; use `snowflake_prod_12345`.
- **Dagster resources are not the connection** — the resource holds config in code; the Orchestra connection holds the same credentials in the UI.
- **dbt Core connections are special** — store both Git repo and warehouse credentials. One per repo+warehouse.
- **Snowflake resource fields** — map directly to Orchestra Snowflake connection fields.
- **GCP service account** — paste the full JSON into the GCP connection key field.
- **Airbyte Cloud vs Server** — `AirbyteCloudResource` -> Cloud connection; `AirbyteResource(host=,port=)` -> Server connection.
- **`EnvVar`** — secrets -> connection; non-secret config -> `inputs:`.

## References

- Orchestra connections: https://docs.getorchestra.io/docs/core-concepts/connections
- Orchestra environments: https://docs.getorchestra.io/docs/core-concepts/environments
- Dagster resources: https://docs.dagster.io/concepts/resources
