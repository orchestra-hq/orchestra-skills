# Pipeline pattern examples

Illustrative Orchestra pipeline patterns. Adapt integrations, connections, and paths to the
target repo. See also `yaml-authoring.md` for schema and validation.

## Personalised Slack reporting (warehouse → LLM → messaging)

**Purpose:** Run a warehouse query, pass results to an LLM prompt, post formatted output to
Slack (or another HTTP destination).

**Stages:**

1. **Warehouse query** — `SNOWFLAKE` / `SNOWFLAKE_RUN_QUERY` (or `GCP_BIG_QUERY`,
   Postgres, Databricks, etc.) with `set_outputs: true` and SQL from `${{ inputs.sql_query }}`
2. **Generate message** — `OPEN_AI` / `OPEN_AI_CHAT` with `context` from
   `${{ ORCHESTRA.PIPELINE_RUN_TASKS['<query-task-id>'].OUTPUTS['results'] }}` and
   `set_outputs: true`; constrain output with `output_schema` when the downstream step expects
   JSON (for example Slack Blocks)
3. **Send** — `HTTP` / `HTTP_REQUEST` `POST` with `body` from the LLM task outputs and an
   HTTP connection for the webhook

**Variations:** any warehouse integration for step 1; any messaging HTTP endpoint for step 3;
any prompt or model for step 2. Enable `webhook` and define `inputs` when the pipeline should
be triggered with ad hoc SQL and prompt text.

**Reference implementation:** `orchestra-hq/orchestra-blueprints` —
`.cursor/pipeline_examples/agents_produce_agents.yaml` and
`orchestra/agentic_analytics_demo.yml` (Claude Agent SDK + MCP tasks).
