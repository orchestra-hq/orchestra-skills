---
name: prefect-secrets-to-orchestra
description: "Use this skill when the user has Prefect Secret blocks, SecretStr fields, SecretDict, or prefect.blocks.system.Secret usage to move into Orchestra. Triggers: any Prefect code using Secret.load(), .get_secret_value(), SecretStr type annotations, or AWS Secrets Manager blocks storing credentials. Never asks for real secret values — produces a checklist of what to re-enter directly in Orchestra."
---

## Overview

This skill produces a **secrets checklist** — a table of every secret name, where it came from in Prefect, and where it must be re-entered in Orchestra. It never asks for actual secret values and never writes them to any file. Prefect's encrypted Secret block store has no bulk export mechanism; every secret must be re-entered by hand in Orchestra.

## Parameter Mapping

| Prefect secret pattern | Orchestra target | Notes |
|---|---|---|
| `Secret.load("api-key").get()` for a SaaS credential | Store on that tool's Orchestra connection credential field | Use `prefect-connections-to-orchestra` to identify the connection |
| `SecretStr` field on a credential block | Store on Orchestra connection credential field | Follow `prefect-connections-to-orchestra` for the block type |
| `Secret` value used inside a `@task` as an env var | Python connection → env var → read via `os.getenv("KEY")` in script | |
| `SecretDict` | Multiple key-value entries on the relevant connection | One Orchestra field per key |
| `AwsSecret` / AWS Secrets Manager block | Orchestra AWS Secrets Manager credential store | Create an Orchestra AWS connection; secret JSON keys must match the target integration's expected fields |
| Prefect Variables (non-sensitive, `Variable.get()`) | Pipeline `inputs:` or task `env_vars:` — **not** secrets | Variables are not encrypted; treat as config, not credentials |

**Hard rule (enforced always):**

> NEVER ask the user to paste real secret values into this chat, and never write real secret values into any file. Produce only a checklist of secret NAMES and where to enter them.

## Orchestra YAML Structure

Secrets themselves do not appear in YAML. The YAML only shows where the secret will be consumed:

```yaml
# Python task reading a secret from env var (set on the connection)
integration: PYTHON
integration_job: PYTHON_EXECUTE_SCRIPT
connection: python_git_prod_12345   # env vars set on this connection in Orchestra UI
parameters:
  command: 'python scripts/call_api.py'
  python_version: '3.12'
```

```python
# scripts/call_api.py — reads secret at runtime from env
import os
import requests

token = os.getenv("MY_API_TOKEN")   # set on the Orchestra Python connection
response = requests.get("https://api.example.com/data", headers={"Authorization": f"Bearer {token}"})
```

## Conversion Steps

- [ ] Search the codebase for: `Secret.load(`, `.get_secret_value()`, `SecretStr`, `SecretDict`, `prefect.blocks.system.Secret`, `AwsSecret`
- [ ] For each hit: record the secret name and how it is used (SaaS credential, env var in task, etc.)
- [ ] Separate Prefect Variables (`Variable.get()`) from Secret blocks — Variables are non-sensitive and go to `inputs:` or `env_vars:`, not Orchestra secrets
- [ ] Produce the secrets checklist (see template below)
- [ ] For each row marked "Orchestra connection field": follow `prefect-connections-to-orchestra` to create the connection and enter the value in the credential field
- [ ] For each row marked "Python connection env var": open the Orchestra Python connection → Advanced → Environment Variables → add the key
- [ ] For AWS Secrets Manager entries: create an Orchestra AWS Secrets Manager connection; confirm the secret's JSON keys match the integration's expected field names
- [ ] After all secrets are entered, verify each pipeline runs successfully in a test environment before promoting to production

## Before / After Example

### Prefect (before)

```python
from prefect.blocks.system import Secret
from prefect import task, flow
from pydantic import SecretStr

@task
def call_external_api():
    token = Secret.load("my-api-token").get()
    response = requests.get("https://api.example.com", headers={"Authorization": f"Bearer {token}"})
    return response.json()

@task
def write_to_snowflake(data):
    # SnowflakeCredentials block holds SecretStr password
    creds = SnowflakeCredentials.load("sf-prod")
    conn = creds.get_client()
    conn.execute("INSERT INTO ...")
```

### Orchestra YAML (after)

```yaml
pipeline:
  stage-fetch:
    tasks:
      call-external-api:
        integration: PYTHON
        integration_job: PYTHON_EXECUTE_SCRIPT
        connection: python_git_prod_12345   # MY_API_TOKEN set on this connection
        parameters:
          command: 'python scripts/call_external_api.py'
          python_version: '3.12'
          set_outputs: true
        depends_on: []

  stage-load:
    tasks:
      write-to-snowflake:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
        connection: snowflake_prod_67890   # password entered in Orchestra UI
        parameters:
          query: "INSERT INTO ..."
        depends_on:
          - call-external-api
```

**Secrets checklist output** (example):

```
| Secret name        | Source Prefect block/pattern          | Orchestra target                                        | Action                                    |
|--------------------|---------------------------------------|---------------------------------------------------------|-------------------------------------------|
| SNOWFLAKE_PASSWORD | SnowflakeCredentials "sf-prod".password | Snowflake connection "snowflake_prod_67890" → password  | Re-enter manually in Orchestra UI         |
| MY_API_TOKEN       | Secret.load("my-api-token")           | Python connection "python_git_prod_12345" → env var MY_API_TOKEN | Re-enter in Python connection JSON   |
| GH_DEPLOY_KEY      | GitHubCredentials "gh-deploy".token   | Python connection "python_git_prod_12345" → deploy key  | Paste private key in Orchestra UI         |
```

## Gotchas

- Prefect's encrypted Secret block store has **no bulk export** to Orchestra — every secret must be re-entered by hand; plan for this in your migration timeline
- Prefect `Variable.get()` values are **not encrypted** — route to `inputs:` or `env_vars:` in the Orchestra pipeline, not to secrets
- `SecretStr` fields inside credential blocks follow `prefect-connections-to-orchestra`, not this skill — they are stored on the connection, not as standalone secrets
- AWS Secrets Manager: the secret's JSON must contain exactly the keys the target integration expects (e.g. for a Snowflake connection: `account`, `user`, `password`, etc.); mismatched keys will silently fail
- Never store secrets in task `env_vars:` in the YAML file itself — only reference connection-level env vars or use Orchestra's secrets integration
- If a `Secret` block is used purely for observability (e.g. masking values in logs) with no downstream consumer, it can be dropped entirely

## References

- https://docs.prefect.io/v3/develop/blocks
- https://docs.getorchestra.io/docs/core-concepts/connections

## Adding Alerts

See `prefect-alerts-to-orchestra` for all notification patterns.
