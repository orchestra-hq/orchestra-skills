"""Report which skill files are behind orchestra-docs and the published pipeline schema.

Run by the `orchestra/sync-docs.yml` pipeline's agent before it edits anything
(see orchestra/sync-docs.md). Deterministic and cheap, so the agent only spends
effort when something a skill depends on actually changed.

- Docs: a skill file depends on every docs page it links to
  (https://docs.getorchestra.io/docs/<path>). Changes are read from
  `git diff <watermark>..HEAD -- docs/` in an orchestra-docs checkout.
- Dead links: linked pages missing from the docs checkout (moved/renamed pages).
- Schema: the published pipeline_model.json is compared against the snapshot
  in scripts/pipeline_model.snapshot.json (enum values + a hash per $def).

Usage:
    python3 scripts/docs_sync.py --docs <orchestra-docs checkout>           # report; exit 2 if anything is stale
    python3 scripts/docs_sync.py --docs <orchestra-docs checkout> --update  # move watermark + snapshot to now
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATERMARK = ROOT / ".docs-sync.json"
SNAPSHOT = ROOT / "scripts" / "pipeline_model.snapshot.json"
SCHEMA_URL = "https://orchestra-hq-public-production.s3.eu-west-2.amazonaws.com/jsonschemas/pipeline_model.json"
DOCS_LINK = re.compile(r"https://docs\.getorchestra\.io/docs/([A-Za-z0-9_\-/.]+)")


def link_to_page(path):
    """`core-concepts/pipelines/schema/#x` -> `docs/core-concepts/pipelines/schema` (extension-less)."""
    return "docs/" + path.split("#")[0].rstrip("/.")


def page_key(docs_file):
    """`docs/a/b.mdx` or `docs/a/b/index.mdx` -> `docs/a/b`, the same key link_to_page produces."""
    key = re.sub(r"\.mdx?$", "", docs_file)
    return key[: -len("/index")] if key.endswith("/index") else key


def dependency_map():
    """{docs page key: [skill files linking to it]} across both plugins."""
    deps = {}
    for f in sorted((ROOT / "skills").rglob("*.md")):
        rel = str(f.relative_to(ROOT))
        for link in set(DOCS_LINK.findall(f.read_text())):
            deps.setdefault(link_to_page(link), []).append(rel)
    return deps


def changed_docs(docs_dir, since):
    out = subprocess.run(
        ["git", "-C", docs_dir, "diff", "--name-only", f"{since}..HEAD", "--", "docs/"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.splitlines() if re.search(r"\.mdx?$", p)]


def docs_pages(docs_dir):
    out = subprocess.run(["git", "-C", docs_dir, "ls-files", "docs/"], capture_output=True, text=True, check=True).stdout
    return {page_key(p) for p in out.splitlines() if re.search(r"\.mdx?$", p)}


def schema_summary(schema):
    """The parts of the schema a sync cares about: every $def's enum values, and a hash of the rest."""
    return {
        name: {"enum": sorted(d["enum"])} if "enum" in d else {"sha": hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]}
        for name, d in schema.get("$defs", {}).items()
    }


def schema_diff(old, new):
    """Added/removed $defs, added/removed enum values, and other changed $defs, between two summaries."""
    diff = {"added_defs": sorted(new.keys() - old.keys()), "removed_defs": sorted(old.keys() - new.keys()), "enums": {}, "changed_defs": []}
    for name in sorted(old.keys() & new.keys()):
        o, n = old[name], new[name]
        if o == n:
            continue
        if "enum" in o and "enum" in n:
            diff["enums"][name] = {"added": sorted(set(n["enum"]) - set(o["enum"])), "removed": sorted(set(o["enum"]) - set(n["enum"]))}
        else:
            diff["changed_defs"].append(name)
    return {k: v for k, v in diff.items() if v}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True, help="path to an orchestra-docs checkout at the commit to sync to")
    ap.add_argument("--update", action="store_true", help="record docs HEAD and the live schema as synced")
    args = ap.parse_args()

    since = json.loads(WATERMARK.read_text())["docs_sha"]
    head = subprocess.run(["git", "-C", args.docs, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    live = schema_summary(json.load(urllib.request.urlopen(SCHEMA_URL, timeout=30)))

    if args.update:
        WATERMARK.write_text(json.dumps({"docs_sha": head}, indent=2) + "\n")
        SNAPSHOT.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n")
        print(f"watermark -> {head}, schema snapshot refreshed")
        return 0

    deps = dependency_map()
    pages = docs_pages(args.docs)
    impacted, unmapped = {}, []
    for docs_file in changed_docs(args.docs, since):
        skills = deps.get(page_key(docs_file))
        if not skills:
            unmapped.append(docs_file)
        for s in skills or []:
            impacted.setdefault(s, []).append(docs_file)

    report = {
        "docs_range": f"{since}..{head}",
        "impacted": impacted,  # skill file -> changed docs pages it links to
        "unmapped_docs_changes": unmapped,  # changed pages no skill links to — review for new YAML features only
        "dead_links": {k: v for k, v in deps.items() if k not in pages},  # linked pages that no longer exist
        "schema": schema_diff(json.loads(SNAPSHOT.read_text()), live),
    }
    print(json.dumps(report, indent=2))
    return 2 if impacted or report["dead_links"] or report["schema"] else 0


if __name__ == "__main__":
    sys.exit(main())
