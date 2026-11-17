#!/usr/bin/env python3
"""Orchestra task: grade one eval case from its two RUN_AGENT task runs.

Takes the upstream task run IDs rather than the agents' outputs, because Orchestra
substitutes templates as raw text and a pipeline YAML can't survive a shell command.
Each agent's reply is read from its session history; the ```yaml block in it is
graded with grade.py. Fails when the with_skill pass rate is below --min-pass-rate.

Usage: python evals/grade_case.py <skill> <case_id> <with_skill_task_run_id>
                                  <without_skill_task_run_id> [--min-pass-rate 0.8]
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import requests

import grade

API = "https://app.getorchestra.io/api"
YAML_BLOCK = re.compile(r"```ya?ml\n(.*?)```", re.S)


def get(path, **params):
    r = requests.get(f"{API}{path}", params=params, timeout=30,
                     headers={"Authorization": f"Bearer {os.environ['ORCHESTRA_API_KEY']}"})
    r.raise_for_status()
    return r.json()


def agent_result(task_run_id: str) -> dict:
    """The final `result` message of the agent session behind a RUN_AGENT task run."""
    session_id = get(f"/engine/public/task_runs/{task_run_id}")["runParameters"]["session_id"]
    page = get(f"/ai/v1/sessions/{session_id}/history/messages",
               before_sequence_id=f"{int(time.time() * 1000) + 60_000}-0", turn_limit=1)
    for msg in reversed(page["results"]):
        data = (msg.get("messagePayload") or {}).get("data") or {}
        if "result" in data:
            return data
    sys.exit(f"No agent result in session {session_id}")


ap = argparse.ArgumentParser()
ap.add_argument("skill")
ap.add_argument("case_id")
ap.add_argument("with_skill_task_run_id")
ap.add_argument("without_skill_task_run_id")
ap.add_argument("--min-pass-rate", type=float, default=0.8)
args = ap.parse_args()

evals = json.loads((grade.EVALS_DIR / args.skill / "evals.json").read_text())
case = next(c for c in evals["evals"] if c["id"] == args.case_id)

rates = {}
for config, task_run_id in (("with_skill", args.with_skill_task_run_id),
                            ("without_skill", args.without_skill_task_run_id)):
    result = agent_result(task_run_id)
    blocks = YAML_BLOCK.findall(result["result"])
    path = Path(tempfile.mkdtemp()) / "pipeline.yml"
    path.write_text(blocks[-1] if blocks else result["result"])
    grading = grade.grade_output(grade.resolve_assertions(case), path)
    rates[config] = grading["summary"]["pass_rate"] or 0
    usage = next(iter((result.get("model_usage") or {}).values()), {})
    print(f"--- {config}: pass_rate={rates[config]} cost=${usage.get('costUSD')} "
          f"output_tokens={usage.get('outputTokens')} duration_ms={result.get('duration_ms')}")
    print(json.dumps(grading, indent=2))

print(f"{args.skill}/{args.case_id}: with_skill={rates['with_skill']} "
      f"without_skill={rates['without_skill']} "
      f"delta={rates['with_skill'] - rates['without_skill']:+.2f}")
sys.exit(0 if rates["with_skill"] >= args.min_pass_rate else 1)
