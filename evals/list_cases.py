#!/usr/bin/env python3
"""Orchestra task: list eval cases as RUN_AGENT prompts for a matrix.

Sets output `cases` = [[skill, case_id, with_skill_prompt, without_skill_prompt], ...].
The with_skill prompt carries SKILL.md (plus linked references) exactly as runner.py
injects it; fixtures are inlined because an Orchestra agent has no files to read.

Usage: python evals/list_cases.py <skill,skill,...>
"""
import json
import os
import sys

import runner

cases = []
for skill in (s.strip() for s in sys.argv[1].split(",") if s.strip()):
    suite_dir = runner.EVALS_DIR / skill
    skill_text = runner.WITH_SKILL_PREAMBLE.format(name=skill, body=runner.skill_body(skill))
    for case in json.loads((suite_dir / "evals.json").read_text())["evals"]:
        files = "".join(f"\n\n----- files/{f} -----\n{(suite_dir / 'files' / f).read_text()}"
                        for f in case.get("files", []))
        prompt = case["prompt"] + files
        cases.append([skill, case["id"], f"{skill_text}\n\n{prompt}", prompt])

print(json.dumps([c[:2] for c in cases], indent=2))
if os.environ.get("ORCHESTRA_API_KEY"):
    from orchestra_sdk.orchestra import OrchestraSDK
    OrchestraSDK(api_key=os.environ["ORCHESTRA_API_KEY"]).set_output("cases", cases)
