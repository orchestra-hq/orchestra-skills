#!/usr/bin/env python3
"""Run a skill eval suite by driving the headless `claude` CLI with and without the skill.

For each eval case and each configuration the runner creates an isolated run directory,
copies the case fixtures into ./files/, and invokes `claude -p` there with MCP servers
disabled and only file tools allowed (so a run can never touch a live warehouse, repo,
or Orchestra). For `with_skill`, the skill's SKILL.md is injected via
--append-system-prompt; `without_skill` is the bare prompt — that pair is the baseline
comparison. Token/duration/cost are captured to timing.json; the final assistant
message to transcript.txt. The iteration is graded on completion (see grade.py).

Usage:
    python3 evals/runner.py <suite> [--only ID] [--configs with_skill,without_skill]
                                    [--iteration N] [--model NAME] [--max-turns N]
                                    [--no-grade]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
SKILLS_ROOT = REPO_ROOT / "skills" / "orchestra" / "skills"
CONFIGS = ("with_skill", "without_skill")

WITH_SKILL_PREAMBLE = (
    "You have been given a Skill below. Follow its instructions to complete the user's "
    "task. Apply only the parts relevant to authoring the pipeline YAML — the environment "
    "has no Snowflake, git, or Orchestra access, so do not attempt to inspect a live "
    "warehouse, push a branch, or deploy; produce the YAML file the task asks for.\n\n"
    "----- BEGIN SKILL: {name} -----\n{body}\n----- END SKILL -----"
)


def skill_body(suite: str) -> str:
    skill_md = SKILLS_ROOT / suite / "SKILL.md"
    if not skill_md.exists():
        sys.exit(f"SKILL.md not found at {skill_md} — suite must match the skill directory name.")
    return skill_md.read_text()


def next_iteration(workspace: Path) -> int:
    workspace.mkdir(parents=True, exist_ok=True)
    nums = [int(p.name.split("-")[1]) for p in workspace.glob("iteration-*")
            if p.name.split("-")[1].isdigit()]
    return max(nums, default=0) + 1


def run_one(case: dict, config: str, run_dir: Path, suite_dir: Path,
            skill_text: str | None, output_file: str, model: str | None,
            max_turns: int) -> None:
    files_dir = run_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for fname in case.get("files", []):
        src = suite_dir / "files" / fname
        if not src.exists():
            sys.exit(f"Fixture not found: {src}")
        shutil.copy(src, files_dir / Path(fname).name)

    cmd = [
        "claude", "-p", case["prompt"],
        "--output-format", "json",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read", "Write", "Edit", "Glob", "Grep",
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--max-turns", str(max_turns),
    ]
    if model:
        cmd += ["--model", model]
    if skill_text is not None:
        cmd += ["--append-system-prompt",
                WITH_SKILL_PREAMBLE.format(name=case.get("_suite", ""), body=skill_text)]

    print(f"  → {case['id']:<28} {config:<14} running…", flush=True)
    proc = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True)
    if proc.returncode != 0:
        (run_dir / "error.txt").write_text(proc.stderr or proc.stdout or "claude exited non-zero")
        print(f"    ! claude exited {proc.returncode}; see {run_dir / 'error.txt'}")
        return

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        (run_dir / "error.txt").write_text(proc.stdout)
        print(f"    ! could not parse claude JSON output; raw saved to {run_dir / 'error.txt'}")
        return

    usage = result.get("usage", {}) or {}
    total_tokens = (usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    + usage.get("cache_creation_input_tokens", 0)
                    + usage.get("cache_read_input_tokens", 0))
    timing = {
        "total_tokens": total_tokens,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "duration_ms": result.get("duration_ms"),
        "num_turns": result.get("num_turns"),
        "total_cost_usd": result.get("total_cost_usd"),
        "is_error": result.get("is_error"),
    }
    (run_dir / "timing.json").write_text(json.dumps(timing, indent=2) + "\n")
    (run_dir / "transcript.txt").write_text(result.get("result", ""))

    produced = run_dir / output_file
    print(f"    done · {total_tokens} tok · {result.get('duration_ms')}ms · "
          + ("wrote " + output_file if produced.exists() else "NO " + output_file))


def main():
    ap = argparse.ArgumentParser(description="Run a skill eval suite headlessly.")
    ap.add_argument("suite", help="suite name == skill directory name")
    ap.add_argument("--only", help="run a single eval id")
    ap.add_argument("--configs", default=",".join(CONFIGS),
                    help="comma-separated configs (with_skill,without_skill)")
    ap.add_argument("--iteration", type=int, help="iteration number (default: next free)")
    ap.add_argument("--model", help="pin a model, e.g. claude-opus-4-8")
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--no-grade", action="store_true", help="skip grading after runs")
    args = ap.parse_args()

    suite_dir = EVALS_DIR / args.suite
    evals_path = suite_dir / "evals.json"
    if not evals_path.exists():
        sys.exit(f"No suite at {evals_path}")
    evals = json.loads(evals_path.read_text())
    output_file = evals.get("output_file", "pipeline.yml")
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    cases = [c for c in evals["evals"] if not args.only or c["id"] == args.only]
    if not cases:
        sys.exit(f"No eval matches --only {args.only!r}")

    body = skill_body(args.suite)
    workspace = EVALS_DIR / ".workspace" / args.suite
    it = args.iteration or next_iteration(workspace)
    iteration_dir = workspace / f"iteration-{it}"
    print(f"Suite {args.suite} · iteration-{it} · {len(cases)} case(s) · configs {configs}")

    for case in cases:
        case["_suite"] = args.suite
        for config in configs:
            run_dir = iteration_dir / case["id"] / config
            run_dir.mkdir(parents=True, exist_ok=True)
            run_one(case, config, run_dir, suite_dir,
                    skill_text=body if config == "with_skill" else None,
                    output_file=output_file, model=args.model, max_turns=args.max_turns)

    if args.no_grade:
        print(f"\nRuns complete. Grade with: python3 evals/grade.py {args.suite} --iteration {it}")
        return

    print("\nGrading…")
    import grade
    grade.grade_iteration(args.suite, iteration_dir, configs)
    print(f"\nDone. Outputs under {iteration_dir}")


if __name__ == "__main__":
    main()
