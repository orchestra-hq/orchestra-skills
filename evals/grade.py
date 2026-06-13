#!/usr/bin/env python3
"""Grade generated pipeline YAML against the assertions in a suite's evals.json.

Coded assertions (those carrying a `check`) are graded mechanically and reliably.
Free-text assertions (only `text`) are recorded as `manual` (passed=null) for human
or LLM review. Writes a grading.json next to each run's output and an aggregated
benchmark.json for the iteration.

Usage:
    python3 evals/grade.py <suite> [--iteration N] [--configs with_skill,without_skill]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.exit("pyyaml is required: pip install -r evals/requirements.txt (or use system python3)")

EVALS_DIR = Path(__file__).resolve().parent
CONFIGS = ("with_skill", "without_skill")


# --- helpers ---------------------------------------------------------------

def iter_tasks(pipeline: dict):
    """Yield every task dict across all groups of a parsed pipeline."""
    if not isinstance(pipeline, dict):
        return
    for group in pipeline.values():
        if isinstance(group, dict):
            for task in (group.get("tasks") or {}).values():
                if isinstance(task, dict):
                    yield task


def dig(obj, path: str):
    """Dotted-path lookup into nested dicts. Returns (found, value)."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


# --- checks ----------------------------------------------------------------
# Each returns (passed: bool, evidence: str). `raw` is the file text, `doc` is the
# parsed YAML (None if it didn't parse).

def _valid_yaml(a, raw, doc):
    if isinstance(doc, dict):
        return True, f"Parsed to a YAML mapping with {len(doc)} top-level keys"
    return False, "File is missing or did not parse to a YAML mapping"


def _yaml_eq(a, raw, doc):
    found, val = dig(doc or {}, a["path"])
    if not found:
        return False, f"Path '{a['path']}' not present"
    ok = val == a["value"]
    return ok, f"{a['path']} = {val!r} (expected {a['value']!r})"


def _yaml_present(a, raw, doc):
    found, _ = dig(doc or {}, a["path"])
    return found, ("present" if found else "missing") + f": {a['path']}"


def _regex(a, raw, doc):
    flags = re.IGNORECASE if a.get("ignore_case") else 0
    n = len(re.findall(a["pattern"], raw, flags))
    need = a.get("min_count", 1)
    return n >= need, f"pattern /{a['pattern']}/ matched {n}x (need {need})"


def _min_task_groups(a, raw, doc):
    groups = (doc or {}).get("pipeline") or {}
    n = len(groups) if isinstance(groups, dict) else 0
    return n >= a["min"], f"{n} task group(s) (need {a['min']}): {list(groups)[:8]}"


def _all_groups_have(a, raw, doc):
    groups = (doc or {}).get("pipeline") or {}
    if not isinstance(groups, dict) or not groups:
        return False, "no task groups found"
    missing = [name for name, g in groups.items() if not (isinstance(g, dict) and a["key"] in g)]
    return not missing, ("all groups have '%s'" % a["key"]) if not missing else f"missing '{a['key']}' in: {missing}"


def _every_task(a, raw, doc):
    tasks = list(iter_tasks((doc or {}).get("pipeline") or {}))
    if not tasks:
        return False, "no tasks found"
    field, want = a["field"], a["equals"]
    bad = [t for t in tasks if dig(t, field)[1] != want]
    return not bad, f"{len(tasks)} task(s), {len(tasks) - len(bad)} with {field}=={want!r}"


def _some_task(a, raw, doc):
    tasks = list(iter_tasks((doc or {}).get("pipeline") or {}))
    field, want = a["field"], a["equals"]
    hits = [t for t in tasks if dig(t, field)[1] == want]
    return bool(hits), f"{len(hits)} task(s) with {field}=={want!r}"


def _alerts_status(a, raw, doc):
    alerts = (doc or {}).get("alerts") or []
    for al in alerts if isinstance(alerts, list) else []:
        if isinstance(al, dict) and a["status"] in (al.get("statuses") or []):
            return True, f"alert '{al.get('name', '?')}' fires on {a['status']}"
    return False, f"no alert configured for status {a['status']}"


def _groups_chained(a, raw, doc):
    groups = (doc or {}).get("pipeline") or {}
    chained = [n for n, g in groups.items() if isinstance(g, dict) and (g.get("depends_on") or [])]
    return bool(chained), f"groups with non-empty depends_on: {chained or 'none'}"


CHECKS = {
    "valid_yaml": _valid_yaml,
    "yaml_eq": _yaml_eq,
    "yaml_present": _yaml_present,
    "regex": _regex,
    "min_task_groups": _min_task_groups,
    "all_groups_have": _all_groups_have,
    "every_task": _every_task,
    "some_task": _some_task,
    "alerts_status": _alerts_status,
    "groups_chained": _groups_chained,
}


# --- grading ---------------------------------------------------------------

def grade_output(assertions, output_path: Path) -> dict:
    raw = output_path.read_text() if output_path.exists() else ""
    doc = None
    if raw:
        try:
            doc = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            doc = None
            raw_err = str(e)
        else:
            raw_err = None
    else:
        raw_err = "output file not found"

    results = []
    coded_pass = coded_total = manual = 0
    for a in assertions:
        check = a.get("check")
        if not check:
            results.append({"text": a["text"], "passed": None, "graded_by": "manual",
                            "evidence": "free-text assertion — review by hand or LLM"})
            manual += 1
            continue
        fn = CHECKS.get(check)
        if fn is None:
            results.append({"text": a["text"], "passed": False, "graded_by": "code",
                            "evidence": f"unknown check type '{check}'"})
            coded_total += 1
            continue
        if doc is None and check != "valid_yaml":
            passed, evidence = False, f"YAML unavailable ({raw_err})"
        else:
            try:
                passed, evidence = fn(a, raw, doc)
            except Exception as e:  # a malformed assertion shouldn't crash the run
                passed, evidence = False, f"check raised: {e}"
        results.append({"text": a["text"], "passed": bool(passed), "graded_by": "code",
                        "evidence": evidence})
        coded_total += 1
        coded_pass += int(bool(passed))

    return {
        "assertion_results": results,
        "summary": {
            "passed": coded_pass,
            "failed": coded_total - coded_pass,
            "coded_total": coded_total,
            "manual": manual,
            "pass_rate": round(coded_pass / coded_total, 4) if coded_total else None,
        },
    }


def grade_iteration(suite: str, iteration_dir: Path, configs) -> dict:
    evals = json.loads((EVALS_DIR / suite / "evals.json").read_text())
    output_file = evals.get("output_file", "pipeline.yml")
    by_config = {c: [] for c in configs}

    for case in evals["evals"]:
        case_dir = iteration_dir / case["id"]
        for config in configs:
            run_dir = case_dir / config
            if not run_dir.exists():
                continue
            grading = grade_output(case["assertions"], run_dir / output_file)
            (run_dir / "grading.json").write_text(json.dumps(grading, indent=2) + "\n")
            timing = {}
            tpath = run_dir / "timing.json"
            if tpath.exists():
                timing = json.loads(tpath.read_text())
            by_config[config].append({
                "eval": case["id"],
                "pass_rate": grading["summary"]["pass_rate"],
                "passed": grading["summary"]["passed"],
                "coded_total": grading["summary"]["coded_total"],
                "manual": grading["summary"]["manual"],
                "tokens": timing.get("total_tokens"),
                "duration_ms": timing.get("duration_ms"),
            })
            print(f"  {case['id']:<28} {config:<14} "
                  f"{grading['summary']['passed']}/{grading['summary']['coded_total']} coded "
                  f"(+{grading['summary']['manual']} manual)")

    def agg(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        if not vals:
            return None
        out = {"mean": round(statistics.fmean(vals), 4)}
        if len(vals) > 1:
            out["stddev"] = round(statistics.stdev(vals), 4)
        return out

    run_summary = {c: {"pass_rate": agg(rows, "pass_rate"),
                       "tokens": agg(rows, "tokens"),
                       "duration_ms": agg(rows, "duration_ms"),
                       "evals": rows}
                   for c, rows in by_config.items() if rows}

    benchmark = {"suite": suite, "iteration": iteration_dir.name, "run_summary": run_summary}
    if all(by_config.get(c) for c in ("with_skill", "without_skill")):
        def m(c, k):
            s = run_summary[c][k]
            return s["mean"] if s else None
        ws, wo = m("with_skill", "pass_rate"), m("without_skill", "pass_rate")
        delta = {}
        if ws is not None and wo is not None:
            delta["pass_rate"] = round(ws - wo, 4)
        for k in ("tokens", "duration_ms"):
            a, b = m("with_skill", k), m("without_skill", k)
            if a is not None and b is not None:
                delta[k] = round(a - b, 2)
        benchmark["delta"] = delta

    (iteration_dir / "benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n")
    return benchmark


def latest_iteration(workspace: Path) -> Path | None:
    its = sorted(workspace.glob("iteration-*"),
                 key=lambda p: int(p.name.split("-")[1]) if p.name.split("-")[1].isdigit() else -1)
    return its[-1] if its else None


def main():
    ap = argparse.ArgumentParser(description="Grade a skill-eval iteration.")
    ap.add_argument("suite")
    ap.add_argument("--iteration", type=int, help="iteration number (default: latest)")
    ap.add_argument("--configs", default=",".join(CONFIGS),
                    help="comma-separated configs to grade")
    args = ap.parse_args()

    workspace = EVALS_DIR / ".workspace" / args.suite
    if args.iteration:
        iteration_dir = workspace / f"iteration-{args.iteration}"
    else:
        iteration_dir = latest_iteration(workspace)
    if not iteration_dir or not iteration_dir.exists():
        sys.exit(f"No iteration to grade under {workspace} — run the runner first.")

    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    print(f"Grading {args.suite} / {iteration_dir.name}")
    benchmark = grade_iteration(args.suite, iteration_dir, configs)

    print("\nbenchmark.json:")
    print(json.dumps(benchmark.get("run_summary", {}), indent=2, default=str))
    if "delta" in benchmark:
        print("delta (with_skill − without_skill):", json.dumps(benchmark["delta"]))
    print(f"\nWrote {iteration_dir / 'benchmark.json'}")


if __name__ == "__main__":
    main()
