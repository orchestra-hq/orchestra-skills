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
SHARED_ASSERTIONS_DIR = EVALS_DIR / "_shared_assertions"


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


def _depends_on_edge(a, raw, doc):
    """check: depends_on_edge — args: group, upstream.

    Asserts a *specific* dependency edge exists (group depends_on upstream), not just
    that chaining exists somewhere (groups_chained only proves that much) — needed to
    verify a migration preserved the actual source topology, not just "some" order.
    """
    groups = (doc or {}).get("pipeline") or {}
    g = groups.get(a["group"])
    if not isinstance(g, dict):
        return False, f"group '{a['group']}' not found"
    deps = g.get("depends_on") or []
    return a["upstream"] in deps, f"{a['group']}.depends_on = {deps} (need '{a['upstream']}')"


def _no_hardcoded_secret(a, raw, doc):
    """check: no_hardcoded_secret — args: extra_keys (optional list[str]).

    Flags secret-shaped YAML keys (api_key/token/password/etc.) holding a literal-looking
    value instead of a ${{ ... }} reference — catches an agent inlining a credential that
    should have become a `connection:` reference instead (see dagster-connections-to-orchestra).
    """
    keys = {"api_key", "secret", "token", "password", "client_secret", "private_key"} | set(a.get("extra_keys", []))
    pattern = r'(?i)\b(' + "|".join(re.escape(k) for k in keys) + r')\b\s*:\s*[\'"]?(?!\$\{\{)[A-Za-z0-9_\-/+=]{8,}'
    hits = re.findall(pattern, raw)
    return not hits, (f"{len(hits)} literal-looking secret field(s): {hits}" if hits
                       else "no literal secret-shaped values")


def _valid_enum(a, raw, doc):
    """check: valid_enum — args: field (dotted path into each task), allowed (list).

    Generalizes every_task/some_task's single-value equality to a whitelist — needed for
    fields with more than one legal value per integration (e.g. Power BI's
    POWER_BI_REFRESH_DATASET vs. POWER_BI_REFRESH_DATAFLOW).
    """
    tasks = list(iter_tasks((doc or {}).get("pipeline") or {}))
    allowed = set(a["allowed"])
    bad = sorted({v for t in tasks for _, v in [dig(t, a["field"])] if v is not None and v not in allowed})
    return not bad, (f"invalid {a['field']} values: {bad}" if bad else f"all {a['field']} in {sorted(allowed)}")


def _alert_destination_requires(a, raw, doc):
    """check: alert_destination_requires — args: integration, field.

    Encodes a destination-specific required-field rule (e.g. SLACK/EMAIL need
    `destination`; PAGER_DUTY/TEAMS/WEBHOOK/DATADOG need `connection_id`) as a real,
    reusable check instead of an unverified free-text assertion.
    """
    alerts = (doc or {}).get("alerts") or []
    found, ok = [], True
    for al in alerts if isinstance(alerts, list) else []:
        for d in (al.get("destinations") or []) if isinstance(al, dict) else []:
            if isinstance(d, dict) and d.get("integration") == a["integration"]:
                found.append(d)
                ok = ok and bool(d.get(a["field"]))
    return (ok and bool(found)), f"{len(found)} {a['integration']} destination(s), field '{a['field']}' present: {ok}"


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
    "depends_on_edge": _depends_on_edge,
    "no_hardcoded_secret": _no_hardcoded_secret,
    "valid_enum": _valid_enum,
    "alert_destination_requires": _alert_destination_requires,
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


def resolve_assertions(case: dict) -> list[dict]:
    """Merge a case's shared category assertions (assertions_ref) ahead of its own.

    assertions_ref names files under evals/_shared_assertions/<ref>.json, each holding
    {"category": ..., "assertions": [...]} in the same object shape used inline — this is
    what lets ~50 suites across categories (alerts, connections, sensors, ...) reuse one
    set of checks instead of hand-copying them per suite. Shared checks come first so
    grading.json reads generic-to-specific; case-specific literals follow.
    """
    assertions = []
    for ref in case.get("assertions_ref", []):
        path = SHARED_ASSERTIONS_DIR / f"{ref}.json"
        if not path.exists():
            sys.exit(f"Unknown assertions_ref '{ref}' in case '{case['id']}' — no {path}")
        assertions += json.loads(path.read_text())["assertions"]
    return assertions + list(case.get("assertions", []))


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
            grading = grade_output(resolve_assertions(case), run_dir / output_file)
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
