---
name: prefect-connections-to-orchestra
description: "Use this skill when converting Prefect code that references blocks holding credentials (SnowflakeCredentials, AwsCredentials, SlackWebhook, or any other loaded via Block.load()), Secret blocks, or environment-variable-based credentials to Orchestra. Triggers: any Prefect block that stores host/login/token/key, any Secret.load()/SecretStr used for credentials, or environment-specific block configuration. Must be read before finalising any Orchestra YAML that contains a connection: field."
---

# Prefect Blocks -> Orchestra Connections

## Overview

Prefect stores credentials in **blocks** — typically loaded via `Block.load("block-name")` or a typed subclass like `SnowflakeCredentials`, `AwsCredentials`, or `SlackWebhook` — registered in the Prefect UI or via `.save()`, with secret fields stored as `SecretStr`. Orchestra connections serve the same purpose but live outside the flow code — set up in the Orchestra UI (Settings -> Connections), or through the public API / Orchestra MCP — and are referenced by name in pipeline YAML. This skill maps common Prefect blocks to their Orchestra equivalents and covers naming, environment patterns, and secrets.

---

## Connection Name Format

```yaml
connection: my_snowflake_12345   # format: descriptive-name_XXXXX (5-digit suffix from UI)
```

The 5-digit suffix is assigned by Orchestra when the connection is created — never invent it. Read it back rather than asking someone to find it: connections are managed through the [public API and the Orchestra MCP server](https://docs.getorchestra.io/docs/core-concepts/tasks/connections#can-i-manage-connections-programmatically) as well as the UI, so listing the workspace's connections returns each one's `descriptive_name_NNNNN` id directly. Fall back to copying it from the UI only where neither is available.

**No block referenced?** If the `@task`/`@flow` doesn't actually load a credentialed block — pure computation, no external client, no secrets — don't invent a connection name or a fake env var placeholder just to fill the field:

```yaml
connection: null   # no distinct block in the source; Orchestra uses the workspace default for this integration
```

Only set a specific `name_XXXXX` or `${{ ENV.VAR }}` when the source code actually references a distinct block/credential.

**This extends to task parameters that duplicate connection-level scope, too** — e.g. Power BI's `workspace_id`, or any other parameter whose value is also stored on the Orchestra connection itself. If the source code just reads the same single value everywhere (one env var, one block-level config field) rather than genuinely varying it per task, leave that parameter `null`/omitted and let the connection's own configured value apply. Only carry an explicit value through (literal, input, or `${{ ENV.VAR }}`) when a specific task truly needs to override it — e.g. targeting a different Power BI workspace than the one configured on the connection.

For environment-specific connections:

```yaml
connection: ${{ ENV.SNOWFLAKE_CONNECTION_NAME }}
```

Set `SNOWFLAKE_CONNECTION_NAME=my_snowflake_12345` in Orchestra's environment settings.

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

**Never hardcode credentials in YAML.** All credentials go in the Orchestra connection — the YAML references only the connection name.

```yaml
# Correct
task-001:
  integration: SNOWFLAKE
  integration_job: SNOWFLAKE_RUN_QUERY
  connection: snowflake_prod_12345
  parameters:
    statement: 'SELECT 1'
```

For secrets stored in a Prefect `Secret` block or `SecretStr` field with no dedicated integration connection (e.g. a bare API token used inside a `PYTHON_EXECUTE_SCRIPT` task), see `prefect-secrets-to-orchestra` for the full checklist-based handoff — this skill covers the connection side, that one covers the "where does each secret land" side.

One case lands back on this side: if the value already sits in **AWS Secrets Manager** or **Azure Key Vault** (an `AwsSecret` block from `prefect-aws`, an `AzureKeyVaultSecretReference` from `prefect-azure`), the Orchestra connection can read it in place rather than holding a copy — set **Credential Store** on the connection and identify the secret by Secret ARN (AWS) or secret name (Azure). The store's own Orchestra connection has to exist first, and the secret's value must be a JSON object with exactly the keys the integration expects. `prefect-secrets-to-orchestra` has the full sequencing; see also [External secret storage](https://docs.getorchestra.io/docs/core-concepts/tasks/connections#external-secret-storage).

---

## Linked Connections — Link, Don't Copy

A `SnowflakeConnector.load("snowflake-prod")` inside a `@task` that also runs arbitrary Python becomes a `PYTHON_EXECUTE_SCRIPT` task (see `python-prefect-to-orchestra`), which needs those warehouse credentials at runtime.

**Decision rule:** if the credential already exists as its own Orchestra connection — the Snowflake/Postgres/AWS connection from the table above — **link** it on the Python/dbt Core connection (**Linked connections** on that connection's form) instead of copying its user/password into that connection's **Secrets**. One credential, one place to rotate it.

Each linked connection's fields arrive as environment variables named `<INTEGRATION>__<CONNECTION_ID>__<FIELD>`: every part upper-cased, each run of non-alphanumeric characters collapsed to a single `_`, and the parts joined by a **double** underscore. `<CONNECTION_ID>` is the id the YAML's `connection:` field uses (it survives renames), and `<FIELD>` is the field's ID from that integration's **Authentication parameters** table — so a Snowflake connection `prod_12345` exports `SNOWFLAKE__PROD_12345__SNOWFLAKE_PASSWORD`.

- Python reads them via the pre-installed SDK: `orchestra.get_linked_connection("snowflake", connection_id="prod_12345")`, keyed by field ID.
- dbt Core reads them in `profiles.yml`: `{{ env_var('SNOWFLAKE__PROD_12345__SNOWFLAKE_PASSWORD') }}`.
- A linked connection that has been deleted, or whose credentials can't be decrypted, is **skipped silently** — its variables are simply absent. Check a variable exists rather than assuming it.
- Linking is also what opens an approved private connection for a task on Orchestra-hosted compute (MariaDB today); private connections are not opened for connections that aren't linked.

Full reference: [Linked connections](https://docs.getorchestra.io/docs/integrations/python#linked-connections) (same section on [dbt Core](https://docs.getorchestra.io/docs/integrations/dbt_core#linked-connections)).

---

## Multi-Environment Pattern

```yaml
pipeline:
  stage-001:
    tasks:
      task-001:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        connection: ${{ ENV.SNOWFLAKE_CONN }}
        parameters:
          statement: 'SELECT * FROM orders LIMIT 10'
```

In Orchestra: Settings -> Environments -> set `SNOWFLAKE_CONN=snowflake_dev_11111` in dev and `snowflake_prod_22222` in prod. This mirrors how Prefect swaps blocks per deployment (e.g. loading `"snowflake-dev"` vs. `"snowflake-prod"` by name).

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
- [ ] Create the connection in Orchestra — UI (Settings -> Connections -> Add Connection), or the public API / Orchestra MCP, which is worth scripting when a deployment carries many blocks
- [ ] If the block's value already lives in AWS Secrets Manager or Azure Key Vault, set **Credential Store** on the connection instead of re-entering the value
- [ ] Note the full connection name including the 5-digit suffix — read it from the create response or by listing connections, not by hand
- [ ] Replace placeholder `connection: <name>` with the real name
- [ ] For environment-specific blocks, set env vars and use `${{ ENV.VAR }}`
- [ ] Never put credentials/tokens in the YAML

---

## Gotchas

- **5-digit suffix is required** — `connection: snowflake_prod` fails; use `snowflake_prod_12345`.
- **Prefect blocks are not the connection** — the block holds config in Prefect's encrypted block store; the Orchestra connection holds the same credentials in Orchestra. There is no bulk export from Prefect's block store, so the Orchestra side being scriptable through the API or MCP doesn't make the migration bulk: each secret still has to be read out of Prefect by hand first — see `prefect-secrets-to-orchestra`.
- **dbt Core connections are special** — store both Git repo and warehouse credentials. One per repo+warehouse.
- **GCP service account** — paste the full JSON into the GCP connection key field.
- **Airbyte Cloud vs Server** — an `AirbyteConnection` block pointed at `api.airbyte.com` -> Cloud connection; pointed at any other host -> Server connection.
- **No official block for Tableau or Power BI** — both are always a hand-rolled `@task` wrapping a third-party client (`tableau-server-client`, `msal`+`requests`); the token-acquisition code disappears entirely once the credentials move to the Orchestra connection.
- **Don't copy a warehouse credential into a Python/dbt connection's Secrets** — if it already exists as its own Orchestra connection, link it and read the injected `<INTEGRATION>__<CONNECTION_ID>__<FIELD>` variables instead.
- **`Variable.get()`** — non-secret, unencrypted config -> `inputs:`; only `Secret`/`SecretStr`-backed values -> a connection.

## References

- Orchestra connections: https://docs.getorchestra.io/docs/core-concepts/tasks/connections
- Managing connections programmatically (public API and MCP): https://docs.getorchestra.io/docs/core-concepts/tasks/connections#can-i-manage-connections-programmatically
- Orchestra external secret storage: https://docs.getorchestra.io/docs/core-concepts/tasks/connections#external-secret-storage
- Orchestra linked connections: https://docs.getorchestra.io/docs/integrations/python#linked-connections
- Orchestra environments: https://docs.getorchestra.io/docs/core-concepts/environments
- Prefect blocks: https://docs.prefect.io/v3/develop/blocks

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
