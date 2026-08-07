#!/usr/bin/env python3
"""Validate already-generated pipeline YAML against the REAL Orchestra schema.

grade.py only checks what a suite's evals.json happens to assert — it never confirms the
YAML would actually be accepted by Orchestra. This script closes that gap by handing an
already-generated pipeline.yml to the real `validate_pipeline` MCP tool (served by the
separately-cloned orchestra-mcp server) and recording whether Orchestra's own schema
validator accepts it.

Deliberately NOT a runner.py flag: runner.py's generation runs are sandboxed on purpose
(`--strict-mcp-config --mcp-config '{"mcpServers":{}}'`, file tools only) so a generation
run can never reach a live system. This script only ever reads files an earlier run
already produced — it never generates YAML itself — and is the one place in the harness
allowed to talk to a real Orchestra MCP server, gated behind an explicit credential.

Usage:
    python3 evals/validate_live.py <suite> [--iteration N] [--configs with_skill,without_skill]

Requires ORCHESTRA_MCP_CONFIG_PATH to point at an MCP config JSON file exposing
orchestra-mcp's `validate_pipeline` tool (its own credentials are that server's concern,
not this script's). Without it, every case is recorded {"status": "skipped"} and the
script exits 0 — a missing credential is never a hard failure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
CONFIGS = ("with_skill", "without_skill")

VALIDATE_PROMPT = (
    "Call the mcp__orchestra__validate_pipeline tool with this exact pipeline definition "
    "as its pipeline_definition argument (parse the YAML below into the JSON structure the "
    "tool expects):\n\n"
    "----- BEGIN PIPELINE YAML -----\n{yaml_text}\n----- END PIPELINE YAML -----\n\n"
    "Report ONLY a single JSON object on the last line of your response, no other text "
    "after it, in exactly this shape: "
    '{{"valid": true|false, "errors": ["..."]}}. '
    "valid is true only if the tool call succeeded with no validation errors; otherwise "
    "false, with the tool's error messages copied into errors."
)


def latest_iteration(workspace: Path) -> Path | None:
    its = sorted(workspace.glob("iteration-*"),
                 key=lambda p: int(p.name.split("-")[1]) if p.name.split("-")[1].isdigit() else -1)
    return its[-1] if its else None


def validate_one(pipeline_path: Path, mcp_config_path: str, model: str | None) -> dict:
    if not pipeline_path.exists():
        return {"status": "skipped", "reason": f"{pipeline_path.name} not found — nothing to validate"}

    yaml_text = pipeline_path.read_text()
    cmd = [
        "claude", "-p", VALIDATE_PROMPT.format(yaml_text=yaml_text),
        "--output-format", "json",
        "--strict-mcp-config", "--mcp-config", mcp_config_path,
        "--allowedTools", "mcp__orchestra__validate_pipeline",
        "--max-turns", "3",
    ]
    if model:
        cmd += ["--model", model]

    proc = subprocess.run(cmd, cwd=pipeline_path.parent, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"status": "ran", "valid": None,
                "errors": [f"claude exited {proc.returncode}: {(proc.stderr or proc.stdout)[:2000]}"]}

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "ran", "valid": None, "errors": [f"could not parse claude output: {proc.stdout[:2000]}"]}

    text = (result.get("result") or "").strip()
    # The model was told to end with a bare JSON object — take the last line that parses.
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        return {"status": "ran", "valid": bool(parsed.get("valid")), "errors": parsed.get("errors", [])}

    return {"status": "ran", "valid": None, "errors": [f"no parseable JSON verdict in response: {text[:2000]}"]}


def main():
    ap = argparse.ArgumentParser(description="Validate generated pipeline YAML against the real Orchestra schema.")
    ap.add_argument("suite")
    ap.add_argument("--iteration", type=int, help="iteration number (default: latest)")
    ap.add_argument("--configs", default=",".join(CONFIGS),
                    help="comma-separated configs to validate (default: with_skill,without_skill)")
    ap.add_argument("--model", help="pin a model for the validating agent")
    args = ap.parse_args()

    mcp_config_path = os.environ.get("ORCHESTRA_MCP_CONFIG_PATH")

    workspace = EVALS_DIR / ".workspace" / args.suite
    iteration_dir = (workspace / f"iteration-{args.iteration}") if args.iteration else latest_iteration(workspace)
    if not iteration_dir or not iteration_dir.exists():
        sys.exit(f"No iteration to validate under {workspace} — run runner.py first.")

    evals = json.loads((EVALS_DIR / args.suite / "evals.json").read_text())
    output_file = evals.get("output_file", "pipeline.yml")
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]

    if not mcp_config_path:
        print("ORCHESTRA_MCP_CONFIG_PATH not set — skipping all live validation "
              "(this is not a failure; static grading via grade.py is unaffected).")

    summary = {"suite": args.suite, "iteration": iteration_dir.name, "results": []}
    for case in evals["evals"]:
        case_dir = iteration_dir / case["id"]
        for config in configs:
            run_dir = case_dir / config
            if not run_dir.exists():
                continue
            if mcp_config_path:
                verdict = validate_one(run_dir / output_file, mcp_config_path, args.model)
            else:
                verdict = {"status": "skipped", "reason": "ORCHESTRA_MCP_CONFIG_PATH not set"}
            (run_dir / "validate_live.json").write_text(json.dumps(verdict, indent=2) + "\n")
            summary["results"].append({"eval": case["id"], "config": config, **verdict})
            status_line = verdict["status"]
            if verdict["status"] == "ran":
                status_line += f" · valid={verdict['valid']}"
                if verdict.get("errors"):
                    status_line += f" · {len(verdict['errors'])} error(s)"
            print(f"  {case['id']:<28} {config:<14} {status_line}")

    (iteration_dir / "live_validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nWrote {iteration_dir / 'live_validation.json'}")


if __name__ == "__main__":
    main()
