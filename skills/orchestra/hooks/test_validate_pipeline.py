#!/usr/bin/env python3
"""Checks for the two branches that decide whether the hook blocks an edit.

Detection must accept a pipeline and reject the YAML that sits beside it in a
repo -- shapes below are trimmed from real files in orchestra-hq/orchestra-blueprints,
and dbt_project.yml is the near miss since it carries both `name` and `version`.
Summarising must return None for anything that is not an actionable rejection,
because a non-None result blocks the agent.
"""

import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate_pipeline import _summarise, is_pipeline

PIPELINE = """
version: v1
name: '[AI AGENT WORKFLOW] Personalised Slack reporting'
pipeline:
  stage-1:
    tasks:
      execute-snowflake-query:
        integration: SNOWFLAKE
        integration_job: SNOWFLAKE_RUN_QUERY
"""

DBT_PROJECT = """
name: bigquery_demo
version: '1.0.0'
profile: bigquery_demo
model-paths: ['models']
"""

DBT_SCHEMA = """
version: 2
models:
  - name: stg_orders
    columns:
      - name: order_id
"""

GITHUB_WORKFLOW = """
name: Trigger Orchestra pipeline
on:
  workflow_dispatch:
jobs:
  trigger:
    runs-on: ubuntu-latest
"""

CASES = {
    "pipeline": (PIPELINE, True),
    "dbt_project.yml": (DBT_PROJECT, False),
    "dbt schema.yml": (DBT_SCHEMA, False),
    "github workflow": (GITHUB_WORKFLOW, False),
    "empty document": ("", False),
    "bare string": ("just text", False),
    "missing pipeline key": ("version: v1\nname: x\n", False),
}


SCHEMA_REJECTION = json.dumps(
    {"detail": [{"loc": ["pipeline", "stage-1", "integration"], "msg": "Input should be 'X'"}]}
)


def check_detection() -> None:
    for label, (document, expected) in CASES.items():
        assert is_pipeline(yaml.safe_load(document)) is expected, f"{label}: expected {expected}"


def check_summarise() -> None:
    assert _summarise(SCHEMA_REJECTION) == "  pipeline.stage-1.integration: Input should be 'X'"

    # A rejection carrying nothing actionable must not block the edit.
    assert _summarise(json.dumps({"detail": []})) is None
    assert _summarise(json.dumps({"detail": [None, 7]})) is None
    assert _summarise("") is None

    # `detail` is a bare string on framework-level errors, not a list of fields.
    assert _summarise(json.dumps({"detail": "Not authenticated"})) == "Not authenticated"

    assert _summarise("<html>502 Bad Gateway</html>") == "<html>502 Bad Gateway</html>"

    long_message = json.dumps({"detail": [{"loc": ["a"], "msg": "x" * 500}]})
    assert len(_summarise(long_message)) < 250


def main() -> None:
    check_detection()
    check_summarise()
    print(f"ok: {len(CASES)} detection cases + summarise")


if __name__ == "__main__":
    main()
