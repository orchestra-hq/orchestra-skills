# Knowledge Store

This file is maintained by the Orchestra **pipeline** skills (`fix-orchestra-pipeline`, `triage-orchestra-pipeline`).
It records past pipeline fixes and discovered patterns — not MCP wiring or REST details (see `references/orchestra/README.md`).

## How this file works

Each time a pipeline is successfully fixed, a new entry is appended under "Fix history".
The skill reads this file during Step 4 (Diagnose) to check if similar errors have been
seen and resolved before. Over time, this builds a knowledge base specific to your
Orchestra workspace — your integrations, your common failure modes, your pipelines.

## Failure frequency profile

_This section is populated on first run by querying recent failed task runs across all
pipelines. It helps the skill prioritise which integration-specific patterns to check first._

## Fix history

_Entries are added here after each successful fix. Newest first._

<!-- TEMPLATE (do not delete):
## Fix: YYYY-MM-DD — [Pipeline Name]
- **Pipeline ID:** [id]
- **Environment:** [env]
- **Error category:** [AUTH_FAILURE | TIMEOUT | QUERY_ERROR | RESOURCE_CONFLICT | NETWORK_ERROR | CONFIG_ERROR | DEPENDENCY_FAILURE | PLATFORM_ERROR | CODE_ERROR | RATE_LIMIT | DATA_ERROR]
- **Integration:** [integration type]
- **Integration job:** [job type]
- **Root cause:** [specific description of what went wrong]
- **Fix applied:** [exact action taken]
- **Was auto-fixed?** [yes/no — did the skill fix it or did the user need to act?]
- **First diagnosis correct?** [yes/no]
- **Notes:** [anything useful for future reference]
-->
