---
name: prefect-connections-to-orchestra
description: "Use this skill when converting Prefect code that references blocks holding credentials (SnowflakeCredentials, AwsCredentials, SlackWebhook, or any other loaded via Block.load()), Secret blocks, or environment-variable-based credentials to Orchestra. Triggers: any Prefect block that stores host/login/token/key, any Secret.load()/SecretStr used for credentials, or environment-specific block configuration. Must be read before finalising any Orchestra YAML that contains a connection: field."
---

# Prefect Blocks -> Orchestra Connections

## Overview

Prefect stores credentials in **blocks** — typically loaded via `Block.load("block-name")` or a typed subclass like `SnowflakeCredentials`, `AwsCredentials`, or `SlackWebhook` — registered in the Prefect UI or via `.save()`, with secret fields stored as `SecretStr`. Orchestra connections serve the same purpose but are configured in the Orchestra UI (Settings -> Connections) and referenced by name in pipeline YAML. This skill maps common Prefect blocks to their Orchestra equivalents and covers naming, environment patterns, and secrets.

---

## Connection Name Format

For the Orchestra-side naming format, `connection: null` fallback, task-parameter-scope caveat, and
environment-specific `${{ ENV.VAR }}` pattern, see the shared reference:
[`../../references/connections.md`](../../references/connections.md).

**No block referenced?** If the `@task`/`@flow` doesn't actually load a credentialed block — pure computation, no external client, no secrets — don't invent a connection name or a fake env var placeholder just to fill the field. Only set a specific `name_XXXXX` or `${{ ENV.VAR }}` when the source code actually references a distinct block/credential.

---

## Block Type Mapping

### Databases

| Prefect block | Orchestra connection type | Key fields |
|---|---|---|
| `SnowflakeCredentials` / `SnowflakeConnector` (`prefect-snowflake`) | **Snowflake** | account, warehouse, database, role, user, password/key pair |
| `DatabricksCredentials` (`prefect-databricks`) | **Databricks** | host (workspace URL), token |
| `GcpCredentials` (`prefect-gcp`) | **GCP Big Query** | service account JSON |
| `AwsCredentials` (`prefect-aws`) | **AWS** | access key ID, secret, region |
| `AzureBlobStorageCredentials` (`prefect-azure`) | **Azure** | tenant, client ID, client secret |
| `SqlAlchemyConnector` against MSSQL (`prefect-sqlalchemy`) | **SQL Server** | host, port, database, user, password |
| `AwsCredentials` used with a Redshift `SqlAlchemyConnector` | **AWS Redshift** | host, port, database, user, password |
| `SqlAlchemyConnector` / custom block against MotherDuck | **MotherDuck** | token |

### Data Integration

| Prefect block | Orchestra connection type | Notes |
|---|---|---|
| `AirbyteConnection` (`prefect-airbyte`) pointed at `api.airbyte.com` | **Airbyte Cloud** | API key |
| `AirbyteConnection` (`prefect-airbyte`) pointed at a self-hosted host | **Airbyte Server** | host URL + API key |
| `FivetranConnector` (`prefect-fivetran`) | **Fivetran** | API key + secret |
| `DbtCoreOperation` / `DbtCliProfile` (`prefect-dbt`) | **dbt Core** | Git repo URL + branch + warehouse creds |
| `DbtCloudCredentials` (`prefect-dbt`) | **dbt Cloud** | API token + account ID |

### Notifications

| Prefect block | Orchestra connection type | Notes |
|---|---|---|
| `SlackWebhook` (`prefect-slack`) | **Slack** | Bot Token (`xoxb-...`) or Incoming Webhook |
| Custom PagerDuty integration (no official block; usually a Prefect Automation action or a hand-rolled `@task`) | **PagerDuty** | integration key |
| `MicrosoftTeamsWebhook` (`prefect.blocks.notifications`) | **Microsoft Teams** | Incoming Webhook URL |
| Email via `prefect.blocks.notifications` / SMTP | **Email** | SMTP host, port, login, password |

### Infrastructure & Protocol

| Prefect block | Orchestra connection type | Notes |
|---|---|---|
| Custom block or plain `@task` wrapping `paramiko`/`fabric` (no official Prefect SSH block) | **Linux SSH** | host, port, username, private key |
| Same, targeting a Windows OpenSSH host | **Windows SSH** | host, port, username, key/password |
| Custom block or plain `@task` wrapping `paramiko.SFTPClient` | **SFTP** | host, port, username, key or password |
| `requests`/`httpx` in a `@task` (HTTP) | **HTTP** | base URL, optional auth headers |
| No official Prefect Tableau block — always a hand-rolled `@task` wrapping `tableau-server-client` | **Tableau Cloud** | server URL, site, PAT |
| No official Prefect Power BI block — always a hand-rolled `@task` wrapping `msal` + `requests` | **Power BI** | tenant ID, client ID, client secret (Azure service principal) |

---

## Secrets Handling

Never hardcode credentials in YAML — see the shared reference for the standard pattern:
[`../../references/connections.md`](../../references/connections.md#secrets-handling).

For secrets stored in a Prefect `Secret` block or `SecretStr` field with no dedicated integration connection (e.g. a bare API token used inside a `PYTHON_EXECUTE_SCRIPT` task), see `prefect-secrets-to-orchestra` for the full checklist-based handoff — this skill covers the connection side, that one covers the "where does each secret land" side.

---

## Multi-Environment Pattern

See the shared reference for the `${{ ENV.VAR }}` pattern and full task example:
[`../../references/connections.md`](../../references/connections.md#environment-specific-connections). This mirrors how Prefect swaps blocks per deployment (e.g. loading `"snowflake-dev"` vs. `"snowflake-prod"` by name).

---

## Prefect Variables -> Orchestra inputs:

Non-credential config (a table name, an environment flag) supplied via a Prefect `Variable` or a typed flow/task parameter should become `inputs:`, not a connection or a secret:

```python
# Prefect
from prefect import flow

@flow
def sync_flow(target_table: str = "orders"):
    ...
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

- [ ] Identify each Prefect block and the secret(s) it holds
- [ ] Find the equivalent Orchestra connection type above
- [ ] Create the connection in Orchestra (Settings -> Connections -> Add Connection)
- [ ] Note the full connection name including the 5-digit suffix
- [ ] Replace placeholder `connection: <name>` with the real name
- [ ] For environment-specific blocks, set env vars and use `${{ ENV.VAR }}`
- [ ] Never put credentials/tokens in the YAML

---

## Gotchas

- **5-digit suffix is required** — `connection: snowflake_prod` fails; use `snowflake_prod_12345`.
- **Prefect blocks are not the connection** — the block holds config in Prefect's encrypted block store; the Orchestra connection holds the same credentials in the UI. There is no bulk export from Prefect's block store — see `prefect-secrets-to-orchestra`.
- **dbt Core connections are special** — store both Git repo and warehouse credentials. One per repo+warehouse.
- **GCP service account** — paste the full JSON into the GCP connection key field.
- **Airbyte Cloud vs Server** — an `AirbyteConnection` block pointed at `api.airbyte.com` -> Cloud connection; pointed at any other host -> Server connection.
- **No official block for Tableau or Power BI** — both are always a hand-rolled `@task` wrapping a third-party client (`tableau-server-client`, `msal`+`requests`); the token-acquisition code disappears entirely once the credentials move to the Orchestra connection.
- **`Variable.get()`** — non-secret, unencrypted config -> `inputs:`; only `Secret`/`SecretStr`-backed values -> a connection.

## References

- Orchestra connections: https://docs.getorchestra.io/docs/core-concepts/connections
- Orchestra environments: https://docs.getorchestra.io/docs/core-concepts/environments
- Prefect blocks: https://docs.prefect.io/v3/develop/blocks

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
